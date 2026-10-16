"""iOS folder picker and persistent access, imported without native dependencies."""
import atexit
import ctypes
import os
import threading

from . import config, data_location

_active_access = None
_delegate_type = None
_pending = {}
_picker_lock = threading.Lock()
_MINIMAL_BOOKMARK = 1 << 9


def _objc():
    import objc_util
    return objc_util


class FolderAccess:
    """Own one URL access scope until a different data location is activated."""
    def __init__(self, url):
        self.url = url.retain()
        self.scoped = False
        try:
            self.path = os.path.abspath(str(url.path()))
            self.scoped = bool(url.startAccessingSecurityScopedResource())
            data = url.bookmarkDataWithOptions_includingResourceValuesForKeys_relativeToURL_error_(
                _MINIMAL_BOOKMARK, None, None, None)
            if not data:
                raise OSError("Cannot remember permission for this folder. Choose it again.")
            self.bookmark = str(data.base64EncodedStringWithOptions_(0))
        except Exception:
            self.close()
            raise

    def metadata(self, folder):
        root = os.path.realpath(self.path)
        selected = os.path.realpath(folder)
        try:
            if os.path.normcase(os.path.commonpath([root, selected])) != os.path.normcase(root):
                return None
        except ValueError:
            return None
        return {"path": folder, "bookmark": self.bookmark,
                "relative_path": os.path.relpath(selected, root)}

    def close(self):
        url, self.url = self.url, None
        if url is not None:
            try:
                if self.scoped:
                    url.stopAccessingSecurityScopedResource()
            finally:
                url.release()


def current_access():
    return _active_access


def activate(access):
    global _active_access
    previous, _active_access = _active_access, access
    if previous is not None and previous is not access:
        previous.close()


atexit.register(activate, None)


def restore_saved_folder(folder):
    """Return (folder, owned access, needs_refresh); caller commits after startup."""
    settings = config.load_settings()
    if "pythonista_data_folder" not in settings:
        return folder, None, False
    try:
        objc = _objc()
    except ImportError:  # Windows and other platforms do not need this capability.
        return folder, None, False
    record = settings["pythonista_data_folder"]
    if not isinstance(record, dict) or record.get("path") != folder:
        raise ValueError("Invalid saved data-folder reference. Choose the folder again.")
    bookmark = record.get("bookmark")
    if not isinstance(bookmark, str) or not bookmark:
        raise ValueError("Invalid saved folder permission. Choose the folder again.")
    data = objc.ObjCClass("NSData").alloc().initWithBase64EncodedString_options_(bookmark, 0)
    if not data:
        raise OSError("The saved folder permission is invalid. Choose the folder again.")
    stale = ctypes.c_bool()
    try:
        url = objc.ObjCClass("NSURL").URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_(
            data, 0, None, ctypes.byref(stale), None)
        if not url:
            raise OSError("The saved folder is unavailable. Authorize or choose the folder again in Pythonista.")
        access = FolderAccess(url)
    finally:
        data.release()
    try:
        relative = record.get("relative_path", ".")
        if not isinstance(relative, str) or os.path.isabs(relative):
            raise ValueError("Invalid saved data-folder reference.")
        selected = os.path.abspath(os.path.join(access.path, relative))
        if access.metadata(selected) is None:
            raise ValueError("The saved data folder is outside its authorized directory.")
        selected = data_location.existing_folder(selected)
    except Exception:
        access.close()
        raise
    return selected, access, stale.value or selected != folder


def request_folder_again(error, initial):
    """Recover permission without opening or creating an inventory first."""
    import console
    try:
        console.alert("Data folder unavailable",
                      "%s\n\nChoose and authorize the data folder again. "
                      "Select the folder containing your inventory. Data will not be copied or moved."
                      % error, "Choose folder")
    except KeyboardInterrupt:  # Cancel: leave settings and data untouched.
        return None
    return pick_folder(initial)


def _pointer(pointer):
    return getattr(pointer, "value", pointer)


def _finish_request(objc, pointer, controller, urls=None):
    request = _pending.pop(_pointer(pointer), None)
    if request is None:
        return
    try:
        if urls is not None:
            urls = objc.ObjCInstance(urls)
            if len(urls) != 1:
                raise ValueError("Choose exactly one folder.")
            request["url"] = urls[0].retain()
    except Exception as exc:
        request["error"] = OSError("Cannot access the selected folder: %s" % exc)
    finally:
        picker = objc.ObjCInstance(controller)
        try:
            picker.setDelegate_(None)
            picker.dismissViewControllerAnimated_completion_(False, None)
        except Exception as exc:
            request["error"] = OSError("Cannot close the folder picker: %s" % exc)
        finally:
            try:
                picker.release()
                request["delegate"].release()
            finally:
                request["event"].set()


def _delegate_class(objc):
    global _delegate_type
    if _delegate_type is None:
        def documentPicker_didPickDocumentsAtURLs_(self, cmd, controller, urls):
            _finish_request(objc, self, controller, urls)

        def documentPickerWasCancelled_(self, cmd, controller):
            _finish_request(objc, self, controller)

        _delegate_type = objc.create_objc_class(
            "YASADataFolderPickerDelegate",
            methods=[documentPicker_didPickDocumentsAtURLs_, documentPickerWasCancelled_],
            protocols=["UIDocumentPickerDelegate"])
    return _delegate_type


def _present_picker(objc, request, initial):
    @objc.on_main_thread
    def present():
        picker = delegate = None
        key = None
        try:
            app = objc.ObjCClass("UIApplication").sharedApplication()
            window = app.keyWindow()
            if not window:
                raise OSError("No active Pythonista window.")
            presenter = window.rootViewController()
            while presenter.presentedViewController():
                presenter = presenter.presentedViewController()
            picker = objc.ObjCClass("UIDocumentPickerViewController").alloc().initWithDocumentTypes_inMode_(
                ["public.folder"], 1)
            picker.setAllowsMultipleSelection_(False)
            picker.setModalPresentationStyle_(0)
            picker.setModalInPresentation_(True)
            if initial and os.path.isdir(initial):
                picker.setDirectoryURL_(objc.ObjCClass("NSURL").fileURLWithPath_(initial))
            delegate = _delegate_class(objc).alloc().init()
            request["delegate"] = delegate
            key = _pointer(delegate.ptr)
            request["key"], request["picker"] = key, picker
            _pending[key] = request
            picker.setDelegate_(delegate)
            presenter.presentViewController_animated_completion_(picker, True, None)
        except Exception as exc:
            _pending.pop(key, None)
            if picker is not None:
                picker.setDelegate_(None)
                picker.release()
            if delegate is not None:
                delegate.release()
            raise OSError("Cannot open the iOS folder picker: %s" % exc) from exc
    present()


def pick_folder(initial=None):
    """Show Files on the main thread and wait on Pythonista's background thread."""
    objc = _objc()
    if objc.ObjCClass("NSThread").isMainThread():
        raise ValueError("The folder picker must be called from a background task.")
    if not _picker_lock.acquire(False):
        raise ValueError("A folder picker is already open.")
    request = {"event": threading.Event(), "url": None, "error": None}
    try:
        _present_picker(objc, request, initial)
        request["event"].wait()
        if request["error"] is not None:
            raise request["error"]
        return FolderAccess(request["url"]) if request["url"] is not None else None
    finally:
        try:
            if not request["event"].is_set():
                @objc.on_main_thread
                def cancel():
                    if request.get("key") in _pending:
                        _finish_request(objc, request["key"], request["picker"])
                cancel()
            if request["url"] is not None:
                request["url"].release()
        finally:
            _picker_lock.release()
