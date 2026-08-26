
def screeshot(container):
    exit_code, output = container.exec_run(
        cmd=["DISPLAY=:1", "python3", "-c", "import pyautogui; pyautogui.screenshot('/tmp/screenshot.png')"]
    )
    if exit_code != 0:
        raise RuntimeError(f"Failed to take screenshot: {output.decode('utf-8')}")
    