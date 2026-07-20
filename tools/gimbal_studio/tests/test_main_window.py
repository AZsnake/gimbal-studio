from importlib.resources import files
from pathlib import Path

from PySide6.QtWidgets import QApplication


APP = QApplication.instance() or QApplication([])
FIXTURE = Path(__file__).parent / "fixtures" / "minimal_bes.ini"


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

    monkeypatch.setattr(main_window_module, "list_ports", lambda: ["COM3", "COM7"])
    window = main_window_module.MainWindow()
    sent = []
    window.serial_link.send_text = sent.append

    assert window.windowTitle() == "Gimbal Studio"
    assert window.brand_label.text() == "Gimbal Studio"
    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "控制",
        "动作组",
        "串口日志",
    ]
    assert [
        window.port_combo.itemText(index)
        for index in range(window.port_combo.count())
    ] == ["COM3", "COM7"]
    assert window.baud_combo.currentText() == "115200"
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

    monkeypatch.setattr(main_window_module, "list_ports", lambda: ["COM3"])
    window = main_window_module.MainWindow()

    def failing_send(_command: str) -> None:
        window.serial_link.error_occurred.emit("write failed")
        raise main_window_module.SerialLinkError("write failed")

    window.serial_link.send_text = failing_send
    window.log_page.command_input.setText("PING")
    window.log_page.send_button.click()

    log_text = window.log_page.log_output.toPlainText()
    assert log_text.count("write failed") == 1
    assert "TX  PING" not in log_text

    window.close()


def test_open_and_save_actions_share_project_between_pages(monkeypatch, tmp_path):
    import gimbal_studio.ui.main_window as main_window_module

    saved_path = tmp_path / "saved.ini"
    monkeypatch.setattr(main_window_module, "list_ports", lambda: [])
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
    window = main_window_module.MainWindow()

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
