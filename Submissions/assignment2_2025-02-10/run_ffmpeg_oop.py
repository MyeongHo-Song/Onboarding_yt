"""
File Name: run_ffmpeg_oop.py
Created Date: 2025.02.10
Programmer: Yuntae Jeon
Description: ffmpeg-based RTSP streaming in OOP style
"""

import cv2
import time

class RTSPstreamer:
    def __init__(self, type, rtsp_url):
        """
        Initialize RTSPstreamer with backend type and RTSP URL.
        
        :param type: str, Backend type [ffmpeg, gstreamer, ...]
        :param rtsp_url: str, RTSP stream URL of the camera
        """
        self.type = type  # Backend type [ffmpeg, gstreamer, ...]
        self.rtsp_url = rtsp_url  # IP 주소

    def server_access(self, try_times, try_interval):
        """
        Attempt to access the RTSP stream server.
        
        :param try_times: int, Number of connection retry attempts
        :param try_interval: int, Waiting time (in seconds) between retries
        :return: cv2.VideoCapture object if successful, else None
        """
        for i in range(try_times):
            cap = cv2.VideoCapture(self.rtsp_url)

            if cap is None:
                print(f"RTSP 서버 접근 실패... Try{i+1}!")
                time.sleep(try_interval)
            else:
                ret, frame = cap.read()
                if not ret or frame is None:
                    print(f"프레임 읽기 실패. 스트림을 재시도합니다... Try{i+1}!")
                    cap.release()
                    time.sleep(try_interval)
                else:
                    return cap
        return None
    
    def visualize_frame(self, frame):
        """
        Display the current frame in a window.
        
        :param frame: numpy.ndarray, Image frame to display
        """
        cv2.imshow("RTSP Stream", frame)
        cv2.waitKey(1)  # 창을 지속적으로 갱신하기 위해 필요

    
    def loop_load_frames(self, try_times, try_interval):
        """
        Continuously load frames from the RTSP stream and display them.
        
        :param try_times: int, Number of connection retry attempts
        :param try_interval: int, Waiting time (in seconds) between retries
        """
        cap = self.server_access(try_times, try_interval)
        if cap is None:
            print("서버 종료")
            return
        
        # RTSP connected
        while True:
            ret, frame = cap.read()

            if not ret or frame is None:
                print("프레임 읽기 실패. 스트림을 재시도합니다...")
                cap = self.server_access(try_times, try_interval)

                if cap is None:
                    print("서버 종료")
                    break

                continue

            self.visualize_frame(frame)

            # 'q' 키를 누르면 종료합니다.
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    type = "ffmpeg"
    rtsp_url = 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101'

    stream = RTSPstreamer(type, rtsp_url)
    stream.loop_load_frames(2, 2)
