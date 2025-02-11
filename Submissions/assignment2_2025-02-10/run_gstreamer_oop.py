"""
File Name: run_gstreamer.py
Created Date: 2025.02.10
Programmer: Yuntae Jeon
Description: gstreamer-based RTSP streaming in OOP style (rtspsrc + appsink)
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import cv2
import numpy as np

class RTSPStreamer:
    def __init__(self, rtsp_url):
        """
        Initialize the RTSPStreamer class.
        
        :param rtsp_url: str, RTSP stream URL of the camera
        """
        self.rtsp_url = rtsp_url
        self.loop = GLib.MainLoop()
        self.pipeline = None
        Gst.init(None)

    def __link_elements(self, *elements):
        """
        Helper function to sequentially link multiple GStreamer elements.
        
        :param elements: list, GStreamer elements to be linked
        :return: bool, True if linking is successful, False otherwise
        """
        for i in range(len(elements) - 1):
            if not elements[i].link(elements[i + 1]):
                print(f"링크 실패: {elements[i].get_name()} -> {elements[i+1].get_name()}")
                return False
        return True

    def __create_pipeline(self):
        """
        Create and configure the GStreamer pipeline using rtspsrc and appsink.
        
        :return: bool, True if pipeline creation is successful, False otherwise
        """
        self.pipeline = Gst.Pipeline.new("rtsp-pipeline")
        if not self.pipeline:
            print("파이프라인 생성 실패")
            return False

        # Create elements
        src    = Gst.ElementFactory.make("rtspsrc", "source")
        depay  = Gst.ElementFactory.make("rtph264depay", "depay")
        parse  = Gst.ElementFactory.make("h264parse", "parse")
        decoder= Gst.ElementFactory.make("avdec_h264", "decoder")
        convert= Gst.ElementFactory.make("videoconvert", "convert")
        sink   = Gst.ElementFactory.make("appsink", "sink")

        if not all([src, depay, parse, decoder, convert, sink]):
            print("요소 생성 실패")
            return False

        # Set RTSP source properties
        src.set_property("location", self.rtsp_url)
        src.set_property("latency", 200)

        # Configure appsink
        sink.set_property("emit-signals", True)
        sink.set_property("sync", False)
        caps = Gst.Caps.from_string("video/x-raw, format=BGR")
        sink.set_property("caps", caps)
        sink.connect("new-sample", self.__on_new_sample)

        # Add elements to pipeline
        self.pipeline.add(src)
        self.pipeline.add(depay)
        self.pipeline.add(parse)
        self.pipeline.add(decoder)
        self.pipeline.add(convert)
        self.pipeline.add(sink)

        # Connect pad-added signal
        src.connect("pad-added", self.__on_pad_added, depay)

        # Link elements in sequence
        if not self.__link_elements(depay, parse, decoder, convert, sink):
            print("정적 요소 링크 실패")
            return False

        return True

    def __on_pad_added(self, src, new_pad, depay):
        """
        Callback function triggered when a new pad is added to rtspsrc.
        
        :param src: GStreamer element, Source element (rtspsrc)
        :param new_pad: GStreamer Pad, Newly created pad
        :param depay: GStreamer element, Depayloader to link to
        """
        print("새 패드 추가:", new_pad.get_name())
        sink_pad = depay.get_static_pad("sink")
        if sink_pad.is_linked():
            print("디페이로더의 sink pad가 이미 링크되어 있음")
            return

        ret = new_pad.link(sink_pad)
        if ret == Gst.PadLinkReturn.OK:
            print("패드 연결 성공")
        else:
            print("패드 연결 실패:", ret)

    def __on_new_sample(self, sink):
        """
        Callback function triggered when a new frame sample is received from appsink.
        
        :param sink: GStreamer element, appsink receiving the frames
        :return: Gst.FlowReturn, Status of the sample processing
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
                print("버퍼 매핑 실패")
                return Gst.FlowReturn.ERROR

            frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape((height, width, 3))
            buf.unmap(map_info)
            GLib.idle_add(self.__visualize_frame, frame)
            return Gst.FlowReturn.OK
        return Gst.FlowReturn.ERROR

    def __visualize_frame(self, frame):
        """
        Display the received frame using OpenCV and stop the loop if 'q' is pressed.
        
        :param frame: numpy.ndarray, Image frame to display
        """
        cv2.imshow("RTSP Stream", frame)
        key = cv2.waitKey(1)
        if key & 0xFF == ord('q'):
            print("종료 키(q)가 입력됨 - 루프 종료")
            self.loop.quit()
        return False

    def __on_message(self, bus, message):
        """
        Handle GStreamer bus messages.
        """
        msg_type = message.type
        if msg_type == Gst.MessageType.EOS:
            print("EOS 도달 - 스트림 종료")
            self.loop.quit()
        elif msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"에러 발생: {err}, {debug}")
            self.loop.quit()
        return True

    def run(self):
        """
        Start the GStreamer pipeline and main event loop.
        """
        if not self.__create_pipeline():
            return

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.__on_message)

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("PLAYING 상태로 전이 실패")
            self.pipeline.set_state(Gst.State.NULL)
            return

        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            self.pipeline.set_state(Gst.State.NULL)
            cv2.destroyAllWindows()
            print("파이프라인 종료")


if __name__ == "__main__":
    rtsp_url = "rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101"
    streamer = RTSPStreamer(rtsp_url)
    streamer.run()
