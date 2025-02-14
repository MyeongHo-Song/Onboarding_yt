import cv2
import time
import multiprocessing

class RTSPStreamer:
    def __init__(self, rtsp_url, window_name, results_dict):
        """
        Initialize the RTSPStreamer instance with the RTSP URL, display window name,
        and a shared dictionary for result reporting.

        :param rtsp_url: str, the RTSP stream URL.
        :param window_name: str, the name for the OpenCV window.
        :param results_dict: dict, a shared dictionary for reporting results.
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

        # Process control.
        self.stopped = False

        # Shared dictionary to report results.
        self.results_dict = results_dict

    def connect_server(self, try_times=5, try_interval=2):
        """
        Attempt to connect to the RTSP stream and read the first frame.
        If successful, create and configure the display window.

        :param try_times: int, the number of connection attempts.
        :param try_interval: int or float, the time interval (in seconds) between attempts.
        :return: bool, True if connection and first frame read successfully, False otherwise.
        """
        attempt = 0
        while attempt < try_times and not self.stopped:
            self.cap = cv2.VideoCapture(self.rtsp_url)
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    self.first_start_time = time.time()
                    print(f"[{self.window_name}] Connected to {self.rtsp_url}")
                    cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(self.window_name, 640, 480)
                    return True
                else:
                    print(f"[{self.window_name}] Failed to read frame on attempt {attempt + 1}")
            else:
                print(f"[{self.window_name}] Failed to connect on attempt {attempt + 1}")
            attempt += 1
            time.sleep(try_interval)
        return False

    def run(self):
        """
        Connect to the RTSP server and continuously capture frames.
        Each frame is overlaid with FPS, latency, frame count, and timestamp, then displayed.

        :return: None
        """
        if not self.connect_server():
            print(f"[{self.window_name}] Unable to connect to {self.rtsp_url}. Exiting process.")
            return

        while not self.stopped:
            current_time = time.time()
            # set to 60 seconds
            if current_time - self.first_start_time >= 60:
                print(f"[{self.window_name}]")
                self.stop()
                break

            capture_time = time.time()
            ret, frame = self.cap.read()
            if not ret:
                print(f"[{self.window_name}] Frame read failed. Exiting process.")
                self.stop()
                break

            self.frame_count += 1
            current_time = time.time()
            latency = current_time - capture_time

            # If this is a new frame (its capture timestamp differs), update display stats.
            if self.last_displayed_timestamp != capture_time:
                self.last_displayed_timestamp = capture_time
                if self.display_start_time is None:
                    self.display_start_time = current_time
                self.display_frame_count += 1

            elapsed_disp = max(current_time - self.display_start_time, 1e-6) if self.display_start_time else 1e-6
            display_fps = self.display_frame_count / elapsed_disp

            # Overlay display FPS, latency, frame count, and current timestamp.
            cv2.putText(frame, f"FPS: {display_fps:.2f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Latency: {latency * 1000:.1f} ms", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            cv2.putText(frame, f"{self.window_name} Frame: {self.frame_count}", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
            cv2.putText(frame, f"Time: {timestamp_str}", (10, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

            cv2.imshow(self.window_name, frame)

            # Allow early termination by pressing 'q' in the stream window.
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.stop()
                break

        # Compute final display FPS from the actual visualized frames.
        if self.display_start_time is not None:
            total_elapsed = time.time() - self.display_start_time
            final_fps = self.display_frame_count / total_elapsed
        else:
            final_fps = 0

        # Report the results in the shared dictionary.
        self.results_dict[self.window_name] = {
            'final_fps': final_fps,
            'total_visualized_frames': self.display_frame_count
        }
        print(f"[{self.window_name}] Final FPS: {final_fps:.2f}, Total Visualized Frames: {self.display_frame_count}")

        if self.cap is not None:
            self.cap.release()
        cv2.destroyWindow(self.window_name)

    def stop(self):
        """
        Stop the capture loop.

        :return: None
        """
        self.stopped = True


def process_streamer(rtsp_url, window_name, results_dict):
    """
    Create an RTSPStreamer instance and run it.

    :param rtsp_url: str, the RTSP stream URL.
    :param window_name: str, the name for the OpenCV window.
    :param results_dict: dict, a shared dictionary for reporting results.
    :return: None
    """
    streamer = RTSPStreamer(rtsp_url, window_name, results_dict)
    streamer.run()


def main():
    # Updated RTSP URL list.
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

    # Use a Manager dictionary for result reporting.
    manager = multiprocessing.Manager()
    results_dict = manager.dict()

    processes = []

    # Create and start a process for each RTSP stream.
    for i, url in enumerate(rtsp_urls):
        window_name = f"Camera {i + 1}"
        p = multiprocessing.Process(target=process_streamer, args=(url, window_name, results_dict))
        p.start()
        processes.append(p)

    # Wait for all processes to finish (each runs for 5 minutes or until stopped by 'q').
    for p in processes:
        p.join()

    # Report the results stored in the shared dictionary.
    for window_name, result in results_dict.items():
        final_fps = result['final_fps']
        total_frames = result['total_visualized_frames']
        print(f"Stream {window_name} - Final FPS: {final_fps:.2f}, Total Visualized Frames: {total_frames}")

if __name__ == "__main__":
    main()
