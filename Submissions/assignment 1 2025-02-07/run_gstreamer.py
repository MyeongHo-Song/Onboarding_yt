#!/usr/bin/env python3
import gi
import time

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

def repeat_access(rtsp_url, try_times, try_interval):
    """RTSP 서버 재접속 시도"""
    for i in range(try_times):
        pipeline = Gst.ElementFactory.make("playbin", "player")
        if not pipeline:
            print(f"playbin 생성 실패... Try {i+1}!")
            time.sleep(try_interval)
            continue

        pipeline.set_property("uri", rtsp_url)
        pipeline.set_state(Gst.State.PLAYING)

        # 2초 동안 상태 확인 (정상 실행 여부)
        time.sleep(2)
        state_change_return, state, _ = pipeline.get_state(5000000000)

        if state == Gst.State.PLAYING:
            return pipeline

        print(f"RTSP 연결 실패... Try {i+1}!")
        pipeline.set_state(Gst.State.NULL)
        time.sleep(try_interval)

    return None

def main():
    Gst.init(None)

    rtsp_url = "rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101"
    try_times = 2
    try_interval = 2

    pipeline = repeat_access(rtsp_url, try_times, try_interval)
    if pipeline is None:
        print("RTSP 서버 연결 실패. 종료합니다.")
        return

    # RTSP 연결 유지 및 재시도
    while True:
        ret, state, _ = pipeline.get_state(5000000000)
        if state != Gst.State.PLAYING:
            print("RTSP 스트림 중단됨. 재접속 시도...")
            pipeline = repeat_access(rtsp_url, try_times, try_interval)
            if pipeline is None:
                print("서버 응답 없음. 종료합니다.")
                break

    pipeline.set_state(Gst.State.NULL)
    print("GStreamer 종료")

if __name__ == "__main__":
    main()
