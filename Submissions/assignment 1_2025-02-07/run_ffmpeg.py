import cv2
import time

def repeat_access(rtsp_url, try_times, try_interval):
    for i in range(try_times):
        cap = cv2.VideoCapture(rtsp_url)

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



def main():
    rtsp_url = 'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101'
    try_times = 2
    try_interval = 2

    cap = repeat_access(rtsp_url, try_times, try_interval)

    if cap is None :
        print("서버 종료")
        return

    # RTSP connected
    while True:
        ret, frame = cap.read()

        # 프레임 읽기에 실패한 경우
        if not ret or frame is None:
            print("프레임 읽기 실패. 스트림을 재시도합니다...")
            cap = repeat_access(rtsp_url, try_times, try_interval)

            if cap is None :
                print("서버 종료")
                break

            continue

        # 읽어온 프레임을 화면에 출력 (원하는 프레임 처리를 여기에 추가)
        cv2.imshow("RTSP Stream", frame)

        # 'q' 키를 누르면 종료합니다.
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
