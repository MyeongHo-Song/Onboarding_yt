"""
File Name: run_ffmpeg_oop.py
Created Date: 2025.02.10
Programmer: Yuntae Jeon
Description: ffmpeg-based RTSP streaming in OOP style
"""

import cv2
import time

class RTSPstreamer:
    def __init__(self, rtsp_url):
        """
        Initialize RTSPstreamer with backend type and RTSP URL.
        
        :param type: str, Backend type [ffmpeg, gstreamer, ...]
        :param rtsp_url: str, RTSP stream URL of the camera
        """
        self.rtsp_url = rtsp_url  
        self.cap = None 

    def __connect_server(self, try_times, try_interval):
        """
        Attempt to access the RTSP stream server.
        
        :param try_times: int, Number of connection retry attempts
        :param try_interval: int, Waiting time (in seconds) between retries
        :return: cv2.VideoCapture object if successful, else None
        """
        for i in range(try_times):
            try:
                cap = cv2.VideoCapture(self.rtsp_url)
                ret, frame = cap.read()
            except Exception as e:
                print(f"예외 발생: {e}. 재시도합니다... Try{i+1}!")
                time.sleep(try_interval)
                continue

            if not ret or frame is None:
                print(f"프레임 읽기 실패. 스트림을 재시도합니다... Try{i+1}!")
                cap.release()
                time.sleep(try_interval)
            else:
                self.cap = cap  # 인스턴스 변수에 저장
                return True
        return False
    
    def __visualize_frame(self, frame):
        """
        Display the current frame in a window.
        
        :param frame: numpy.ndarray, Image frame to display
        """
        cv2.imshow("RTSP Stream", frame)

    def run(self, try_times, try_interval):
        """
        Continuously load frames from the RTSP stream and display them.
        
        :param try_times: int, Number of connection retry attempts
        :param try_interval: int, Waiting time (in seconds) between retries
        """
        if not self.__connect_server(try_times, try_interval):
            print("서버 종료")
            return
        
        while True:
            ret, frame = self.cap.read()

            if not ret or frame is None:
                print("프레임 읽기 실패. 스트림을 재시도합니다...")
                self.cap.release()
                if not self.__connect_server(try_times, try_interval):
                    print("서버 종료")
                    break
                continue

            self.__visualize_frame(frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("종료 키(q)가 입력됨 - 루프 종료")
                break

        self.cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    rtsp_url = 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101'

    streamer = RTSPstreamer(rtsp_url)
    streamer.run(2, 2)
