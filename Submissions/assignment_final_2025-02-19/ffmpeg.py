"""
File Name: ffmpeg.py
Created Date: 2025.02.19
Programmer: Yuntae Jeon
Description: Single-camera rtsp connections using ffmpeg
"""

import cv2
import time

class FFmpegSingleCam:
    def __init__(self, rtsp_url, window_name):
        """
        Initialize an FFmpeg-based single camera stream.
        """
        self.rtsp_url = rtsp_url
        self.window_name = window_name

        self.__cap = None
        self.__first_start_time = None
        self.frame_count = 0
        self.read_start_time = None
        self.__latest_frame = None
        self.__latest_timestamp = None

    def connect_cam(self, try_times=5, try_interval=2.0):
        """
        Attempt to connect to the RTSP stream and grab the first frame.

        :param try_times: int, Number of connection attempts.
        :param try_interval: float, Seconds between attempts.
        :return: bool, True if connected successfully, otherwise False.
        """
        for attempt in range(try_times):
            try:
                cap = cv2.VideoCapture(self.rtsp_url)
                ret, frame = cap.read()
            except Exception as e:
                print("[{}] Exception: {}. Retrying... Try {}!".format(
                    self.window_name, e, attempt + 1))
                time.sleep(try_interval)
                continue

            if not ret or frame is None:
                print("[{}] Failed to read frame. Retrying... Try {}!".format(
                    self.window_name, attempt + 1))
                cap.release()
                time.sleep(try_interval)
            else:
                self.__cap = cap
                if self.__first_start_time is None:
                    self.__first_start_time = time.time()
                self.__latest_frame = frame
                self.__latest_timestamp = time.time()
                return True

        print("[{}] Connection failed.".format(self.window_name))
        return False

    def grab_frame(self, timeout=1.0):
        """
        Synchronously capture a new frame from the stream.

        :param timeout: float, Maximum time in seconds to wait for a frame.
        :return: tuple, (frame, timestamp) if successful, or None on timeout/failure.
        """
        start_time = time.time()
        while True:
            if self.__cap is None:
                print("[{}] No capture device available.".format(self.window_name))
                return None

            ret, frame = self.__cap.read()
            if ret and frame is not None:
                self.__latest_frame = frame
                self.__latest_timestamp = time.time()
                self.frame_count += 1

                # Mark the read_start_time on the second frame
                if self.frame_count == 2 and self.read_start_time is None:
                    self.read_start_time = self.__latest_timestamp

                return frame, self.__latest_timestamp

            if time.time() - start_time > timeout:
                print("[{}] grab_frame timeout.".format(self.window_name))
                return None
            time.sleep(0.01)

    def get_frame(self):
        """
        Get the latest frame without clearing it.

        :return: tuple, (frame, timestamp) if available, otherwise None.
        """
        if self.__latest_frame is not None and self.__latest_timestamp is not None:
            return self.__latest_frame, self.__latest_timestamp
        return None

    def release(self):
        """
        Release the video capture resource.

        :return:
        """
        if self.__cap is not None:
            self.__cap.release()
            self.__cap = None
