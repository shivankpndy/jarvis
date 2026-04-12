import cv2
from pygrabber.dshow_graph import FilterGraph

def get_camera_names():
    """Get camera names using DirectShow"""
    graph = FilterGraph()
    devices = graph.get_input_devices()
    return devices

def test_camera(index):
    """Try connecting to a camera index"""
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)

    if not cap.isOpened():
        return False

    ret, frame = cap.read()
    cap.release()

    return ret

def main():
    print("\nScanning cameras...\n")

    camera_names = get_camera_names()

    for i, name in enumerate(camera_names):
        status = "FAILED"

        if test_camera(i):
            status = "CONNECTED"

        print(f"[Index {i}] {name} -> {status}")

    print("\nScan complete.")

if __name__ == "__main__":
    main()