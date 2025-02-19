"""
File Name: gstreamer.py
Created Date: 2025.02.19
Programmer: Yuntae Jeon
Description: Single-camera rtsp connections using gstreamer
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np
import time
import cv2
Gst.init(None)

class GStreamerSingleCam:
    def __init__(self, rtsp_url, window_name):
        """
        단일 RTSP 연결을 위한 GStreamer 객체를 초기화합니다.
        
        :param rtsp_url: RTSP URL.
        :param window_name: OpenCV 디스플레이에 사용할 고유 창 이름.
        """
        self.rtsp_url = rtsp_url
        self.window_name = window_name
        self.pipeline = None
        self.loop = None

        # 최신 프레임을 저장할 변수 (버퍼리스 공유)
        self.latest_frame = None

        # 프레임 카운터
        self.frame_count = 0
        self.first_frame_time = None


    def __link_elements(self, *elements):
        """여러 GStreamer 요소들을 순차적으로 연결합니다."""
        for i in range(len(elements) - 1):
            if not elements[i].link(elements[i + 1]):
                print(f"[{self.window_name}] Failed linking {elements[i].get_name()} -> {elements[i+1].get_name()}")
                return False
        return True

    def __create_pipeline(self):
        """GStreamer 파이프라인을 생성하고 구성합니다."""
        self.pipeline = Gst.Pipeline.new(f"pipeline-{self.window_name}")
        if not self.pipeline:
            print(f"[{self.window_name}] Pipeline creation failed")
            return False

        # 파이프라인 요소 생성
        src     = Gst.ElementFactory.make("rtspsrc", "source")
        depay   = Gst.ElementFactory.make("rtph264depay", "depay")
        parse   = Gst.ElementFactory.make("h264parse", "parse")
        decoder = Gst.ElementFactory.make("avdec_h264", "decoder")
        convert = Gst.ElementFactory.make("videoconvert", "convert")
        sink    = Gst.ElementFactory.make("appsink", "sink")

        if not all([src, depay, parse, decoder, convert, sink]):
            print(f"[{self.window_name}] Failed to create one or more elements")
            return False

        # 요소 구성
        src.set_property("location", self.rtsp_url)
        src.set_property("latency", 10)

        sink.set_property("emit-signals", True)
        sink.set_property("sync", False)
        sink.set_property("max-buffers", 1)
        sink.set_property("drop", True)
        caps = Gst.Caps.from_string("video/x-raw, format=BGR")
        sink.set_property("caps", caps)
        sink.connect("new-sample", self.__on_new_sample)

        # 파이프라인에 요소 추가
        self.pipeline.add(src)
        self.pipeline.add(depay)
        self.pipeline.add(parse)
        self.pipeline.add(decoder)
        self.pipeline.add(convert)
        self.pipeline.add(sink)

        # rtspsrc의 동적 패드 연결
        src.connect("pad-added", self.__on_pad_added, depay)

        if not self.__link_elements(depay, parse, decoder, convert, sink):
            print(f"[{self.window_name}] Static element linking failed")
            return False

        return True

    def __on_pad_added(self, src, new_pad, depay):
        """RTSP 소스의 동적 패드를 depayloader에 연결합니다."""
        sink_pad = depay.get_static_pad("sink")
        if sink_pad.is_linked():
            return
        ret = new_pad.link(sink_pad)
        if ret != Gst.PadLinkReturn.OK:
            print(f"[{self.window_name}] Pad linking failed: {ret}")

    def __on_new_sample(self, sink):
        """
        새 샘플(프레임)이 도착했을 때 호출되는 콜백.
        프레임을 디코딩하여 최신 프레임 변수에 저장합니다.
        """
        sample = sink.emit("pull-sample")
        if sample:
            buf = sample.get_buffer()
            caps = sample.get_caps()
            structure = caps.get_structure(0)
            width = structure.get_value("width")
            height = structure.get_value("height")

            success, map_info = buf.map(Gst.MapFlags.READ)
            if not success:
                print(f"[{self.window_name}] Buffer mapping failed")
                return Gst.FlowReturn.ERROR

            # NumPy 배열로 변환
            frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape((height, width, 3))
            buf.unmap(map_info)

            now = time.time()
            if self.first_frame_time is None:
                self.first_frame_time = now
            self.frame_count += 1

            # 최신 프레임 업데이트
            self.latest_frame = (frame, now)
            return Gst.FlowReturn.OK
        return Gst.FlowReturn.ERROR

    def __on_message(self, bus, message):
        """GStreamer 버스 메시지를 처리합니다."""
        t = message.type
        if t == Gst.MessageType.EOS:
            print(f"[{self.window_name}] End-Of-Stream")
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"[{self.window_name}] Error: {err}, {debug}")
        return True

    def connect_cam(self):
        """
        RTSP URL로 카메라에 연결합니다.
        파이프라인을 생성하고 PLAYING 상태로 전환합니다.
        """
        if not self.__create_pipeline():
            return False

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.__on_message)

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print(f"[{self.window_name}] Unable to set pipeline to PLAYING")
            self.pipeline.set_state(Gst.State.NULL)
            return False

        # GLib MainContext를 수동으로 돌릴 준비 완료
        return True

    def grab_frame(self, timeout=1.0):
        """
        연결된 RTSP 스트림으로부터 프레임 하나를 가져옵니다.
        GLib MainContext를 순회하면서 새로운 프레임 도착을 대기합니다.
        
        :param timeout: 프레임 대기 최대 시간 (초)
        :return: (frame, timestamp) 튜플 또는 timeout 시 None 반환.
        """
        start_time = time.time()
        while self.latest_frame is None:
            # GLib 이벤트를 처리
            GLib.MainContext.default().iteration(False)
            if time.time() - start_time > timeout:
                print(f"[{self.window_name}] grab_frame timeout.")
                return None
        # 최신 프레임을 가져오고 내부 버퍼를 초기화합니다.
        frame_data = self.latest_frame
        self.latest_frame = None
        return frame_data

    def get_frame(self):
        """
        현재 저장된 최신 프레임을 반환합니다.
        (프레임은 초기화되지 않습니다.)
        
        :return: (frame, timestamp) 튜플 또는 None.
        """
        return self.latest_frame
    

if __name__ == "__main__":
    Gst.init(None)
    rtsp_url = "rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101"
    window_name = "Test Stream"
    gs = GStreamerSingleCam(rtsp_url, window_name)
    
    if gs.connect_cam():
        while True:
            # grab_frame()을 통해 프레임 하나씩 가져오기
            frame_data = gs.grab_frame(timeout=2.0)
            if frame_data is not None:
                frame, ts = frame_data
                cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(window_name, 640, 480)
                cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    cv2.destroyAllWindows()