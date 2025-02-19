"""
File Name: multicam_visualizer.py
Created Date: 2025.02.19
Programmer: Yuntae Jeon
Description: Multi-camera visualizer using rtsp connections like ffmpeg, gstreamer
"""

import time
import cv2
import threading
import multiprocessing
from gi.repository import GLib

from gstreamer import GStreamerSingleCam
from ffmpeg import FFmpegSingleCam


class MultiCamVisualizer:
    def __init__(self):
        """
        Initialize the MultiCamVisualizer.

        :return:
        """
        self.stream_type = "gstreamer"   # "gstreamer" or "ffmpeg"
        self.run_mode = "seq"           # "seq", "multithread", or "multiproc"
        self.meas_type = "vis"          # "read" or "vis"
        self.duration = 60              # Duration in seconds

        self.__streamers = []
        self.__is_visualized = True
        self.__display_frame_counts = {}
        self.__display_start_times = {}
        self.__last_displayed_timestamps = {}

    def set_settings(self, stream_type="gstreamer", run_mode="seq", meas_type="vis", duration=60):
        """
        Set or update public settings for the visualizer.

        :param stream_type: string, The type of stream ("gstreamer" or "ffmpeg").
        :param run_mode: string, The running mode ("seq", "multithread", or "multiproc").
        :param meas_type: string, The measurement type ("read" or "vis").
        :param duration: int, The duration in seconds.
        :return:
        """
        self.stream_type = stream_type
        self.run_mode = run_mode
        self.meas_type = meas_type
        self.duration = duration
        self.__is_visualized = (meas_type != "read")

    def connect_cameras(self, stream_type, urls):
        """
        Attempt to connect to each RTSP URL and set up a window if visualization is enabled.

        :param stream_type: string, Which streamer implementation to use ("gstreamer" or "ffmpeg").
        :param urls: list, A list of RTSP URLs.
        :return:
        """
        print("Setting up camera connections...")
        self.__streamers = []
        for idx, url in enumerate(urls):
            window_name = "Stream {}".format(idx + 1)
            if stream_type == "gstreamer":
                streamer = GStreamerSingleCam(url, window_name)
            elif stream_type == "ffmpeg":
                streamer = FFmpegSingleCam(url, window_name)
            else:
                print("Unknown stream type:", stream_type)
                continue

            if streamer.connect_cam():
                self.__streamers.append(streamer)
                if self.__is_visualized:
                    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(window_name, 640, 480)
                self.__display_frame_counts[window_name] = 0
                self.__display_start_times[window_name] = None
                self.__last_displayed_timestamps[window_name] = None
            else:
                print("Failed to connect:", url)

    def __display_frame(self, window_name, frame, sample_time):
        """
        Overlay FPS, latency, and time information on the frame and display it.

        :param window_name: string, Name of the window to update.
        :param frame: numpy.ndarray, The frame image.
        :param sample_time: float, Timestamp when this frame was captured.
        :return:
        """
        if self.__last_displayed_timestamps.get(window_name) == sample_time:
            return
        self.__last_displayed_timestamps[window_name] = sample_time

        self.__display_frame_counts[window_name] += 1
        frame_copy = frame.copy()
        current_time = time.time()

        if (self.__display_frame_counts[window_name] == 2 and
                self.__display_start_times.get(window_name) is None):
            self.__display_start_times[window_name] = current_time

        if self.__display_start_times[window_name] is not None:
            elapsed = current_time - self.__display_start_times[window_name]
            if elapsed > 0:
                display_fps = (self.__display_frame_counts[window_name] - 1) / elapsed
            else:
                display_fps = 0.0
        else:
            display_fps = 0.0

        latency = (current_time - sample_time) * 1000  # milliseconds
        timestamp = time.strftime("%H:%M:%S", time.localtime())

        cv2.putText(frame_copy, "Display FPS: {:.2f}".format(display_fps), (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame_copy, "Latency: {:.1f} ms".format(latency), (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(frame_copy,
                    "{} Frame: {}".format(window_name, self.__display_frame_counts[window_name]),
                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.putText(frame_copy, "Time: {}".format(timestamp), (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

        cv2.imshow(window_name, frame_copy)

    def __run_sequential(self):
        """
        Run the visualization in single-threaded (sequential) mode.

        :return:
        """
        print("Running in sequential mode...")
        start_time = time.time()
        while time.time() - start_time < self.duration:
            for streamer in self.__streamers:
                frame_data = streamer.grab_frame(timeout=1.0)
                if self.__is_visualized and frame_data is not None:
                    frame, ts = frame_data
                    self.__display_frame(streamer.window_name, frame, ts)

            if self.__is_visualized and (cv2.waitKey(1) & 0xFF == ord('q')):
                break

            if self.stream_type == "gstreamer":
                GLib.MainContext.default().iteration(False)
                time.sleep(0.005)

        if self.__is_visualized:
            cv2.destroyAllWindows()

    def __capture_loop(self, streamer, duration, display=True):
        """
        Run the common capture and display loop for a single streamer.

        :param streamer: object, A camera streamer (FFmpegSingleCam or GStreamerSingleCam).
        :param duration: int, How long to run, in seconds.
        :param display: bool, Whether to display the frames.
        :return: dict, Contains local display stats (frame count, start time).
        """
        start_time = time.time()
        local_display_count = 0
        local_display_start = None

        while time.time() - start_time < duration:
            capture_time = time.time()
            frame_data = streamer.grab_frame(timeout=1.0)
            if frame_data is None:
                print("[{}] Failed to grab frame. Exiting loop.".format(streamer.window_name))
                break
            frame, _ = frame_data

            if display:
                self.__display_frame(streamer.window_name, frame, capture_time)
                if local_display_count == 0:
                    local_display_count = 1
                elif local_display_start is None:
                    local_display_start = time.time()
                    local_display_count += 1
                else:
                    local_display_count += 1

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        return {
            'display_frame_count': local_display_count,
            'display_start_time': local_display_start
        }

    def __run_multithread(self):
        """
        Run capture in multiple threads, each pulling frames for its own streamer.

        :return:
        """
        print("Running in multithread mode...")
        threads = []
        start_time = time.time()

        for streamer in self.__streamers:
            thread = threading.Thread(
                target=self.__capture_loop,
                args=(streamer, self.duration, False),
                daemon=True
            )
            thread.start()
            threads.append(thread)

        while time.time() - start_time < self.duration:
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            time.sleep(0.01)

        for thread in threads:
            thread.join()

        if self.__is_visualized:
            cv2.destroyAllWindows()

    def __process_streamer(self, rtsp_url, window_name, results_dict):
        """
        Multiprocess worker function that connects, captures, and calculates FPS.

        :param rtsp_url: string, The RTSP URL for the camera.
        :param window_name: string, A name for the display window.
        :param results_dict: dict, A shared dictionary for storing results.
        :return:
        """
        if self.stream_type == "gstreamer":
            streamer = GStreamerSingleCam(rtsp_url, window_name)
        elif self.stream_type == "ffmpeg":
            streamer = FFmpegSingleCam(rtsp_url, window_name)
        else:
            print("Unknown stream type:", self.stream_type)
            return

        if not streamer.connect_cam():
            print("[{}] Unable to connect. Exiting process.".format(window_name))
            return

        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 640, 480)
        loop_data = self.__capture_loop(streamer, self.duration, display=self.__is_visualized)

        # Visualization FPS
        if loop_data['display_start_time']:
            elapsed_vis = time.time() - loop_data['display_start_time']
            if elapsed_vis > 0:
                vis_fps = (loop_data['display_frame_count'] - 1) / elapsed_vis
            else:
                vis_fps = 0.0
        else:
            vis_fps = 0.0

        # Read FPS
        if hasattr(streamer, 'read_start_time') and streamer.read_start_time:
            elapsed_read = time.time() - streamer.read_start_time
            if elapsed_read > 0:
                read_fps = (streamer.frame_count - 1) / elapsed_read
            else:
                read_fps = 0.0
        else:
            read_fps = 0.0

        results_dict[window_name] = {
            'vis_fps': vis_fps,
            'read_fps': read_fps,
            'total_frames': streamer.frame_count
        }

        streamer.release()
        cv2.destroyWindow(window_name)

    def __run_multiprocess(self):
        """
        Run capture in separate processes for each streamer.

        :return:
        """
        print("Running in multiprocessing mode...")
        manager = multiprocessing.Manager()
        results_dict = manager.dict()
        processes = []

        for streamer in self.__streamers:
            process = multiprocessing.Process(
                target=self.__process_streamer,
                args=(streamer.rtsp_url, streamer.window_name, results_dict)
            )
            process.start()
            processes.append(process)

        for process in processes:
            process.join()

        print("Multiprocessing results:")
        for window_name, result in results_dict.items():
            print("{} - Vis FPS: {:.2f}, Read FPS: {:.2f}, Total Frames: {}".format(
                window_name, result['vis_fps'], result['read_fps'], result['total_frames']
            ))

    def __evaluate_visual_fps(self):
        """
        Calculate and print the visualization FPS (main process).

        :return:
        """
        for window_name, count in self.__display_frame_counts.items():
            start = self.__display_start_times.get(window_name)
            if start:
                elapsed = time.time() - start
                if elapsed > 0:
                    fps = (count - 1) / elapsed
                else:
                    fps = 0.0
                print("[{}] Visualization FPS: {:.2f} (Frames: {})".format(window_name, fps, count))
            else:
                print("[{}] Visualization FPS: Not enough frames to compute FPS.".format(window_name))

    def __evaluate_read_fps(self):
        """
        Calculate and print the read FPS using each streamer's counters.

        :return:
        """
        for streamer in self.__streamers:
            if hasattr(streamer, 'read_start_time') and streamer.read_start_time:
                elapsed = time.time() - streamer.read_start_time
                if elapsed > 0:
                    fps = (streamer.frame_count - 1) / elapsed
                else:
                    fps = 0.0
                print("[{}] Read FPS: {:.2f} (Total frames: {})".format(
                    streamer.window_name, fps, streamer.frame_count))
            else:
                print("[{}] Read FPS: Not enough frames to compute FPS.".format(streamer.window_name))

    def __evaluate_fps(self):
        """
        Evaluate and print both read and visualization FPS.

        :return:
        """
        if self.meas_type == "read":
            self.__evaluate_read_fps()
        else:
            self.__evaluate_read_fps()
            self.__evaluate_visual_fps()

    def run(self):
        """
        Run the visualization based on the selected run_mode and evaluate FPS.

        :return:
        """
        if self.run_mode == "seq":
            self.__run_sequential()
            self.__evaluate_fps()
        elif self.run_mode == "multithread":
            self.__run_multithread()
            self.__evaluate_fps()
        elif self.run_mode == "multiproc":
            self.__run_multiprocess()


def main():
    """
    Main function to set settings, connect cameras, and start visualization.

    :return:
    """
    urls = [
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/201',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/301',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/401',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/501',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/601',
    ]

    visualizer = MultiCamVisualizer()
    visualizer.set_settings(stream_type="ffmpeg", run_mode="seq", meas_type="vis", duration=60)
    visualizer.connect_cameras(visualizer.stream_type, urls)
    visualizer.run()


if __name__ == "__main__":
    main()
