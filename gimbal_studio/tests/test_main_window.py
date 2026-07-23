from importlib.resources import files
from pathlib import Path

from PySide6.QtWidgets import QApplication


APP = QApplication.instance() or QApplication([])
FIXTURE = Path(__file__).parent / "fixtures" / "minimal_bes.ini"


def _stub_devices(monkeypatch, serial_ports=None, hid_devices=None):
    import gimbal_studio.ui.main_window as main_window_module

    serial_ports = list(serial_ports or [])
    hid_devices = list(hid_devices or [])
    monkeypatch.setattr(
        main_window_module.TransportRouter,
        "enumerate_devices",
        staticmethod(lambda: (serial_ports, hid_devices)),
    )


def test_theme_qss_is_package_resource():
    from gimbal_studio.app import load_theme

    theme_path = files("gimbal_studio") / "resources" / "theme.qss"
    assert theme_path.is_file()
    assert load_theme() == theme_path.read_text(encoding="utf-8")


def test_theme_uses_graphite_amber_palette():
    from gimbal_studio.app import load_theme

    theme = load_theme()

    assert "#141414" in theme
    assert "#1e1e1e" in theme
    assert "#f3f3f0" in theme
    assert "#e8a54b" in theme


def test_theme_prefers_cjk_capable_font_before_segoe():
    """Chinese UI must not rely on Segoe UI fallback (uneven size/weight)."""
    from gimbal_studio.app import load_theme

    theme = load_theme()
    family_line = next(
        line.strip()
        for line in theme.splitlines()
        if line.strip().startswith("font-family:")
    )
    assert "Microsoft YaHei" in family_line
    assert family_line.index("Microsoft YaHei") < family_line.index("Segoe UI")


def test_theme_labels_use_transparent_background():
    """Labels must not paint graphite boxes over the lighter top bar."""
    from gimbal_studio.app import load_theme
    import re

    theme = load_theme()
    match = re.search(
        r"QLabel\s*\{[^}]*background-color:\s*([^;]+);",
        theme,
        flags=re.DOTALL,
    )
    assert match is not None
    assert match.group(1).strip() == "transparent"


def test_pick_ui_font_prefers_installed_cjk_family():
    from gimbal_studio.app import pick_ui_font
    from PySide6.QtGui import QFontDatabase

    font = pick_ui_font()
    available = set(QFontDatabase.families())
    if "Microsoft YaHei UI" in available or "Microsoft YaHei" in available:
        assert "YaHei" in font.family()
    else:
        assert font.pointSize() == 10


def test_log_page_emits_commands_and_clears_log():
    from gimbal_studio.ui.log_page import LogPage

    page = LogPage()
    submitted = []
    page.submit_command.connect(submitted.append)

    page.append_received("READY\n")
    page.command_input.setText("#000P1500T1000!")
    page.send_button.click()

    assert submitted == ["#000P1500T1000!"]
    assert "RX  READY" in page.log_output.toPlainText()
    assert page.command_input.text() == ""

    page.clear_button.click()
    assert page.log_output.toPlainText() == ""


def test_main_window_builds_shell_and_wires_serial(monkeypatch):
    import gimbal_studio.ui.main_window as main_window_module

    _stub_devices(monkeypatch, serial_ports=["COM3", "COM7"])
    window = main_window_module.MainWindow(autoload=False)
    sent = []

    def capture_send(command: str) -> None:
        sent.append(command)
        window.serial_link.sent.emit(command)

    window.serial_link.send_text = capture_send

    assert window.windowTitle() == "Gimbal Studio"
    assert window.brand_label.text() == "Gimbal Studio"
    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "控制",
        "动作组",
        "通信日志",
    ]
    assert [
        window.port_combo.itemText(index)
        for index in range(window.port_combo.count())
    ] == ["COM3", "COM7"]
    assert window.baud_combo.currentText() == "115200"
    assert [
        window.baud_combo.itemText(index)
        for index in range(window.baud_combo.count())
    ] == [
        "1200",
        "2400",
        "4800",
        "9600",
        "14400",
        "19200",
        "38400",
        "57600",
        "115200",
        "230400",
        "460800",
        "921600",
    ]
    assert window.tabs.widget(0) is window.control_page
    assert window.control_page.current_pose() == {0: 1500, 1: 1500}

    window.log_page.command_input.setText("PING")
    window.log_page.send_button.click()

    assert sent == ["PING"]
    assert "TX  PING" in window.log_page.log_output.toPlainText()

    window.serial_link.received.emit("PONG")
    assert "RX  PONG" in window.log_page.log_output.toPlainText()

    window.serial_link.connection_changed.emit(True)
    assert window.connect_button.text() == "断开"
    assert window.status_dot.property("connected") is True

    window.close()


def test_send_failure_logs_error_once(monkeypatch):
    import gimbal_studio.ui.main_window as main_window_module

    _stub_devices(monkeypatch, serial_ports=["COM3"])
    window = main_window_module.MainWindow(autoload=False)

    def failing_send(_command: str) -> None:
        window.serial_link.error_occurred.emit("write failed")
        raise main_window_module.TransportError("write failed")

    window.serial_link.send_text = failing_send
    window.log_page.command_input.setText("PING")
    window.log_page.send_button.click()

    log_text = window.log_page.log_output.toPlainText()
    assert log_text.count("write failed") == 1
    assert "TX  PING" not in log_text

    window.close()


def test_connection_state_controls_sequence_actions(monkeypatch):
    import gimbal_studio.ui.main_window as main_window_module
    from gimbal_studio.project.models import ActionGroup, Project

    _stub_devices(monkeypatch, serial_ports=["COM3"])
    window = main_window_module.MainWindow(autoload=False)
    window.set_project(Project(groups=[ActionGroup(0, [(0, 1500, 1000)])]))

    assert not window.groups_page.online_button.isEnabled()
    assert not window.groups_page.offline_button.isEnabled()
    assert not window.groups_page.download_button.isEnabled()

    window.serial_link.connection_changed.emit(True)
    assert window.groups_page.online_button.isEnabled()
    assert window.groups_page.offline_button.isEnabled()
    assert window.groups_page.download_button.isEnabled()

    window.serial_link.connection_changed.emit(False)
    assert window.connect_button.text() == "连接"
    assert window.status_dot.property("connected") is False
    assert not window.groups_page.online_button.isEnabled()
    assert not window.groups_page.offline_button.isEnabled()
    assert not window.groups_page.download_button.isEnabled()

    window.close()


def test_add_group_while_disconnected_keeps_sequence_actions_disabled(
    monkeypatch,
) -> None:
    import gimbal_studio.ui.main_window as main_window_module

    _stub_devices(monkeypatch, serial_ports=["COM3"])
    window = main_window_module.MainWindow(autoload=False)

    assert not window.serial_link.is_connected
    assert not window.project.groups
    assert not window.groups_page.online_button.isEnabled()
    assert not window.groups_page.offline_button.isEnabled()
    assert not window.groups_page.download_button.isEnabled()

    window.groups_page.add_button.click()

    assert window.project.groups
    assert not window.groups_page.online_button.isEnabled()
    assert not window.groups_page.offline_button.isEnabled()
    assert not window.groups_page.download_button.isEnabled()

    window.close()


def test_connection_failure_shows_message_box(monkeypatch):
    import gimbal_studio.ui.main_window as main_window_module

    _stub_devices(monkeypatch, serial_ports=["COM3"])
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "critical",
        lambda _parent, title, message: messages.append((title, message)),
    )
    window = main_window_module.MainWindow(autoload=False)
    monkeypatch.setattr(
        window.serial_link,
        "connect",
        lambda _port, _baud: (_ for _ in ()).throw(
            main_window_module.TransportError("port busy")
        ),
    )

    window.connect_button.click()

    assert messages == [("连接失败", "port busy")]
    assert window.connect_button.text() == "连接"
    window.close()


def test_disconnect_button_returns_ui_to_connect_state(monkeypatch) -> None:
    import gimbal_studio.ui.main_window as main_window_module
    from gimbal_studio.serial_io.port import SerialLink

    class FakeSerial:
        def __init__(self) -> None:
            self.is_open = True

        def close(self) -> None:
            self.is_open = False

        def write(self, data: bytes) -> int:
            return len(data)

        def read(self, size: int = 1) -> bytes:
            return b""

    _stub_devices(monkeypatch, serial_ports=["COM3"])
    window = main_window_module.MainWindow(autoload=False)
    link = SerialLink(window.serial_link)
    window.serial_link._active = link
    window.serial_link._attach_active_signals(link)
    link.attach_for_test(FakeSerial())

    assert window.connect_button.text() == "断开"

    window.connect_button.click()

    assert window.serial_link.is_connected is False
    assert window.connect_button.text() == "连接"
    assert window.status_dot.property("connected") is False
    window.close()


def test_can_connect_with_manually_entered_port_when_scan_is_empty(monkeypatch):
    import gimbal_studio.ui.main_window as main_window_module

    _stub_devices(monkeypatch, serial_ports=[], hid_devices=[])
    window = main_window_module.MainWindow(autoload=False)
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        window.serial_link,
        "connect",
        lambda port, baud: calls.append((port, baud)),
    )
    window.port_combo.setEditText("  COM9  ")

    assert window.connect_button.isEnabled()
    window.connect_button.click()

    assert calls == [("COM9", 115200)]
    window.close()


def test_hid_device_is_listed_and_connects_without_baud(monkeypatch):
    import gimbal_studio.ui.main_window as main_window_module

    hid = {
        "display": "HID: STM32 Custm HID",
        "path": b"\\\\?\\hid#vid_0483&pid_5750",
    }
    _stub_devices(monkeypatch, serial_ports=["COM3"], hid_devices=[hid])
    window = main_window_module.MainWindow(autoload=False)
    calls: list[object] = []
    monkeypatch.setattr(
        window.serial_link,
        "connect_hid",
        lambda path: calls.append(path),
    )

    assert [
        window.port_combo.itemText(index)
        for index in range(window.port_combo.count())
    ] == ["HID: STM32 Custm HID", "COM3"]
    assert window.port_combo.currentText() == "HID: STM32 Custm HID"
    assert not window.baud_combo.isEnabled()

    window.connect_button.click()
    assert calls == [hid["path"]]
    window.close()


def test_open_and_save_actions_share_project_between_pages(monkeypatch, tmp_path):
    import gimbal_studio.ui.main_window as main_window_module

    saved_path = tmp_path / "saved.ini"
    _stub_devices(monkeypatch, serial_ports=[])
    monkeypatch.setattr(
        main_window_module.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(FIXTURE), "INI 工程 (*.ini)"),
    )
    monkeypatch.setattr(
        main_window_module.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(saved_path), "INI 工程 (*.ini)"),
    )
    window = main_window_module.MainWindow(autoload=False)

    window.open_action.trigger()

    assert window.control_page.project is window.project
    assert window.groups_page.project is window.project
    assert window.groups_page.table.rowCount() == 2
    assert window.current_path == FIXTURE

    window.control_page.time_spin.setValue(700)
    window.groups_page.add_button.click()
    assert {move[2] for move in window.project.groups[-1].moves} == {700}

    window.project.groups[0].moves[0] = (0, 1234, 500)
    window.save_as_action.trigger()

    assert saved_path.exists()
    assert "#000P1234T0500!" in saved_path.read_text(encoding="utf-8")
    assert window.current_path == saved_path

    window.close()


def test_view_menu_has_pad_focus_action(monkeypatch):
    import gimbal_studio.ui.main_window as main_window_module

    _stub_devices(monkeypatch)
    window = main_window_module.MainWindow(autoload=False)

    assert window.pad_focus_action is not None
    assert window.pad_focus_action.isCheckable()
    assert window.pad_focus_action.text() == "专注控制盘"
    assert not window.pad_focus_action.isChecked()
    assert not window.is_pad_focus()

    menus = [action.text() for action in window.menuBar().actions()]
    assert "视图" in menus

    window.close()


def test_pad_focus_hides_chrome_shrinks_window_and_keeps_same_pad(monkeypatch):
    import gimbal_studio.ui.main_window as main_window_module
    from PySide6.QtCore import QRect

    _stub_devices(monkeypatch)
    window = main_window_module.MainWindow(autoload=False)
    window.setGeometry(QRect(80, 60, 1100, 720))
    pad_before = window.control_page.pad
    full_geo = window.geometry()

    window.pad_focus_action.trigger()

    assert window.is_pad_focus()
    assert window.pad_focus_action.isChecked()
    assert window.menuBar().isHidden()
    assert window.top_bar.isHidden()
    assert window.tabs.isHidden()
    assert not window.pad_focus_host.isHidden()
    assert not window.exit_pad_focus_button.isHidden()
    assert window.exit_pad_focus_button.text() == "退出专注"
    assert window.control_page.pad is pad_before
    assert window.pad_focus_host.isAncestorOf(pad_before)
    assert window.width() <= 420
    assert window.height() <= 420

    window.exit_pad_focus_button.click()

    assert not window.is_pad_focus()
    assert not window.pad_focus_action.isChecked()
    assert not window.menuBar().isHidden()
    assert not window.top_bar.isHidden()
    assert not window.tabs.isHidden()
    assert window.pad_focus_host.isHidden()
    assert window.control_page.pad is pad_before
    assert window.control_page.isAncestorOf(pad_before)
    assert window.geometry() == full_geo

    window.pad_focus_action.trigger()
    window.exit_pad_focus_button.click()
    assert not window.is_pad_focus()
    assert window.control_page.pad is pad_before

    window.close()


def test_main_window_loads_cwd_config_on_startup(monkeypatch, tmp_path):
    import gimbal_studio.ui.main_window as main_window_module
    from gimbal_studio.project.defaults import ensure_default_config
    from PySide6.QtCore import QSettings

    _stub_devices(monkeypatch)
    ensure_default_config(tmp_path / "config.ini")
    store = QSettings("STABLIZER-test", "GimbalStudio-startup-cwd")
    store.clear()
    monkeypatch.chdir(tmp_path)

    window = main_window_module.MainWindow(settings_store=store)

    assert window.current_path == (tmp_path / "config.ini").resolve()
    assert len(window.project.groups) >= 20
    assert window.windowTitle().endswith("config.ini")
    window.close()


def test_main_window_prefers_last_path_over_cwd(monkeypatch, tmp_path):
    import gimbal_studio.ui.main_window as main_window_module
    from gimbal_studio.project.defaults import ensure_default_config
    from gimbal_studio.project.startup import set_last_project_path
    from PySide6.QtCore import QSettings

    _stub_devices(monkeypatch)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    ensure_default_config(cwd / "config.ini")
    last = tmp_path / "remembered.ini"
    ensure_default_config(last)
    store = QSettings("STABLIZER-test", "GimbalStudio-startup-last")
    store.clear()
    set_last_project_path(last, store)
    monkeypatch.chdir(cwd)

    window = main_window_module.MainWindow(settings_store=store)

    assert window.current_path == last.resolve()
    window.close()


def test_main_window_remembers_opened_project(monkeypatch, tmp_path):
    import gimbal_studio.ui.main_window as main_window_module
    from gimbal_studio.project.defaults import ensure_default_config
    from gimbal_studio.project.startup import get_last_project_path
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QFileDialog

    _stub_devices(monkeypatch)
    ensure_default_config(tmp_path / "config.ini")
    other = tmp_path / "other.ini"
    ensure_default_config(other)
    store = QSettings("STABLIZER-test", "GimbalStudio-remember")
    store.clear()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(other), "INI")),
    )

    window = main_window_module.MainWindow(settings_store=store)
    window.open_project()

    assert window.current_path == other.resolve()
    assert Path(get_last_project_path(store)).resolve() == other.resolve()
    window.close()
