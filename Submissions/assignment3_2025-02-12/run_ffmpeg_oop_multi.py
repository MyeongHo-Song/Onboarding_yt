"""
File Name: run_ffmpeg_oop_multi.py
Created Date: 2025.02.11
Programmer: Yuntae Jeon
Description: ffmpeg-based RTSP streaming in OOP style with multiple windows, without threading
"""

import cv2
import time

class RTSPStreamer:
    def __init__(self, rtsp_url, window_name):
        """
        Initialize RTSPStreamer with the RTSP URL and the display window name.
        """
        self.rtsp_url = rtsp_url
        self.window_name = window_name
        self.cap = None

    def visualize_frame(self, frame):
        """
        Display the given frame in the designated window.
        """
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 640, 480)
        cv2.imshow(self.window_name, frame)

    def connect_server(self, try_times, try_interval):
        """
        Attempt to connect to the stream, read the first frame, and display it.
        Combines the connection and initialization logic into a single method.

        :param try_times: int, number of retry attempts.
        :param try_interval: int, seconds to wait between retries.
        :return: bool, True if initialization was successful; otherwise False.
        """
        for attempt in range(try_times):
            try:
                cap = cv2.VideoCapture(self.rtsp_url)
                ret, frame = cap.read()
            except Exception as e:
                print(f"예외 발생 ({self.window_name}): {e}. 재시도합니다... Try {attempt + 1}!")
                time.sleep(try_interval)
                continue

            if not ret or frame is None:
                print(f"프레임 읽기 실패 ({self.window_name}). 재시도합니다... Try {attempt + 1}!")
                cap.release()
                time.sleep(try_interval)
            else:
                self.cap = cap
                self.visualize_frame(frame)
                return True

        print(f"서버 연결 실패 ({self.window_name})")
        return False

    def read_next_frame(self):
        """
        Read the next frame from the stream.

        :return: tuple (bool, frame), where bool indicates success.
        """
        if self.cap is None:
            return False, None
        return self.cap.read()

    def release(self):
        """Release the video capture resources."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None


def process_streamers(active_streamers, try_times=2, try_interval=2):
    """
    Continuously read and display frames for all active streamers.

    :param active_streamers: list of RTSPStreamer instances that are active.
    :param try_times: int, number of retry attempts for reconnecting.
    :param try_interval: int, seconds between retries.
    """
    while True:
        # Iterate over a copy of the list since we may remove streamers.
        for streamer in active_streamers[:]:
            ret, frame = streamer.read_next_frame()
            if not ret or frame is None:
                print(f"프레임 읽기 실패 ({streamer.window_name}). 스트림 재시도 중...")
                streamer.release()
                if not streamer.connect_server(try_times, try_interval):
                    active_streamers.remove(streamer)
                    continue
            else:
                streamer.visualize_frame(frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("종료 키(q)가 입력됨 - 루프 종료")
            break


def main():
    rtsp_urls = [
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/201',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/301',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/401',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/501',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/601',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/701',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/201',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/301',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/401',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/501',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/601',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/701',
    ]

    # Create streamer instances from the list of URLs.
    all_streamers = []
    for idx, url in enumerate(rtsp_urls, start=1):
        window_name = f"Stream_{url.split('/')[-1]}_id={idx}"
        all_streamers.append(RTSPStreamer(url, window_name))

    # Initialize each streamer and keep only those that successfully connect.
    active_streamers = []
    for streamer in all_streamers:
        if streamer.connect_server(2, 2):  # 2 retries, 2 seconds apart
            active_streamers.append(streamer)

    try:
        process_streamers(active_streamers, try_times=2, try_interval=2)
    except KeyboardInterrupt:
        print("\n키보드 인터럽트 감지. 종료합니다...")
    finally:
        # Cleanup: release all streamers and close all windows.
        for streamer in all_streamers:
            streamer.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
