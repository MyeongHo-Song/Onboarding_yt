"""
File Name: run_ffmpeg_oop_multi_thread_report.py
Created Date: 2025.02.13
Programmer: Yuntae Jeon
Description: ffmpeg-based multiple RTSP streamings with thread.
             This version measures FPS and reports for 5 minutes.
"""

import cv2
import time
import threading


class RTSPStreamer:
    def __init__(self, rtsp_url, window_name):
        """
        Initialize the RTSPStreamer instance with the RTSP URL and display window name.

        :param rtsp_url: str, the RTSP stream URL.
        :param window_name: str, the name for the OpenCV window.
        """
        self.rtsp_url = rtsp_url
        self.window_name = window_name
        self.cap = None
        self.first_start_time = None  # Time when first successful connection occurred
        self.frame_count = 0          # Total frames successfully read

         # Attributes for display-based FPS measurement.
        self.last_displayed_timestamp = None  # Timestamp of the last new frame displayed.
        self.display_frame_count = 0          # Count of new frames that have been displayed.
        self.display_start_time = None        # Time when the first new frame was displayed.

        # Create and configure the OpenCV window once during initialization.
        # cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        # cv2.resizeWindow(self.window_name, 640, 480)

        # Shared data for bufferless frame sharing.
        self.latest_frame = None
        self.latest_timestamp = None
        self.lock = threading.Lock()

        # Thread control.
        self.stopped = False
        self.thread = None

    @staticmethod
    def visualize_frame(window_name, frame):
        """
        Display the provided frame in the designated window.

        :param frame: numpy.ndarray, the image/frame to display.
        """
        cv2.imshow(window_name, frame)

    def connect_server(self, try_times, try_interval):
        """
        Attempt to connect to the RTSP stream and read the first frame.
        If successful, start the capture thread.

        :param try_times: int, the number of connection attempts.
        :param try_interval: int or float, the time interval (in seconds) between attempts.
        :return: bool, True if connection and first frame read successfully, False otherwise.
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
                if self.first_start_time is None:
                    self.first_start_time = time.time()
                # Initialize the latest frame and timestamp.
                with self.lock:
                    self.latest_frame = frame
                    self.latest_timestamp = time.time()
                # Start the capture thread.
                self.stopped = False
                self.thread = threading.Thread(target=self._capture_loop, daemon=True)
                self.thread.start()
                # self.visualize_frame(frame)
                return True

        print(f"서버 연결 실패 ({self.window_name})")
        return False

    def _capture_loop(self):
        """
        Continuously capture frames from the RTSP stream and update the shared latest frame.
        This method runs in a separate thread until stopped.
        """
        while not self.stopped:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                with self.lock:
                    self.latest_frame = frame
                    self.latest_timestamp = time.time()
                self.frame_count += 1
            # else:
            #     # Small sleep to prevent a tight loop in case of read failure.
            #     time.sleep(0.01)

    def release(self):
        """
        Stop the capture thread and release the video capture resource.
        """
        self.stopped = True
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        if self.cap is not None:
            self.cap.release()
            self.cap = None


def process_streamers(active_streamers, duration=300):
    """
    Continuously display the latest frames from all active streamers for the given duration.
    Overlays FPS (based on how many new frames are actually displayed)

    :param active_streamers: list, a list of streamer objects containing frame data and metadata.
    :param duration: int or float, the total time (in seconds) to run the streaming process. Default is 300 seconds (5 minutes).
    """
    print("Active thread count:", threading.active_count())
    print("Active threads:", threading.enumerate())

    overall_start = time.time()
    while time.time() - overall_start < duration:
        # Iterate over a copy since the list may change during processing.
        for idx, streamer in enumerate(active_streamers[:]):
            # Safely retrieve the latest frame and its capture timestamp.
            with streamer.lock:
                frame = streamer.latest_frame
                capture_time = streamer.latest_timestamp

            if frame is None:
                print(f"프레임 없음 ({streamer.window_name}).")
                continue

            current_time = time.time()
            # Calculate latency: time elapsed since the frame was captured.
            latency = current_time - capture_time

            # Check if this is a new frame (i.e. its capture timestamp differs).
            if streamer.last_displayed_timestamp != capture_time:
                streamer.last_displayed_timestamp = capture_time
                # Start the display timer if this is the first new frame.
                if streamer.display_start_time is None:
                    streamer.display_start_time = current_time
                streamer.display_frame_count += 1

            # Calculate FPS based solely on how many new frames have been passed to cv2.imshow.
            elapsed_disp = max(current_time - streamer.display_start_time, 1e-6)
            display_fps = streamer.display_frame_count / elapsed_disp

            # Overlay FPS and latency on the frame.
            cv2.putText(frame, f"FPS: {display_fps:.2f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Latency: {latency * 1000:.1f} ms", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # Overlay frame count and current timestamp.
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            cv2.putText(frame, f"{streamer.window_name} Frame: {streamer.frame_count}", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
            cv2.putText(frame, f"Time: {timestamp}", (10, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

            # print(idx)
            # Display the frame.
            cv2.namedWindow(streamer.window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(streamer.window_name, 640, 480)
            cv2.imshow(streamer.window_name, frame)
            # streamer.visualize_frame(streamer.window_name, frame)

            # streamer.visualize_frame(f"Stream_101_id={idx}", frame)
            # streamer.visualize_frame("Stream", frame)

        # Allow manual termination on 'q' key press.
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("종료 키(q)가 입력됨 - 루프 종료")
            break

    print("지정된 시간(5분)이 경과하여 스트리밍을 종료합니다.")



def main():
    rtsp_urls = [
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/201',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/301',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/401',
        # 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/501',
        # 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/601',
        # 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/701',
        # 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101',
        # 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/201',
        # 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/301',
        # 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/401',
        # 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/501',
        # 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/601',
        # 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/701',
    ]

    # Create streamer instances from the RTSP URLs.
    all_streamers = []
    for idx, url in enumerate(rtsp_urls, start=1):
        window_name = f"Stream_{url.split('/')[-1]}_id={idx}"
        all_streamers.append(RTSPStreamer(url, window_name))

    # Initialize each streamer and keep only those that successfully connect.
    active_streamers = []
    for streamer in all_streamers:
        if streamer.connect_server(try_times=2, try_interval=2):
            active_streamers.append(streamer)

    # Run the streaming process for 5 minutes (300 seconds).
    try:
        process_streamers(active_streamers, duration=60)
    except KeyboardInterrupt:
        print("\n키보드 인터럽트 감지. 종료합니다...")
    finally:
        # Report average Display FPS for each streamer.
        end_time = time.time()
        print("\n--- FPS 측정 결과 (Display FPS 기준) ---")
        for streamer in all_streamers:
            if streamer.display_start_time is not None:
                display_total_time = end_time - streamer.display_start_time
                display_fps = streamer.display_frame_count / display_total_time if display_total_time > 0 else 0.0
                print(f"{streamer.window_name} - 평균 Display FPS: {display_fps:.2f} (총 Display 프레임: {streamer.display_frame_count})")
            else:
                print(f"{streamer.window_name} - 연결 실패 혹은 Display 프레임 없음")
        # Cleanup: release all streamers and close all windows.
        for streamer in all_streamers:
            streamer.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
