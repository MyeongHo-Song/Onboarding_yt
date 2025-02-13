"""
File Name: run_gstreamer_oop_multi_report.py
Created Date: 2025.02.12
Programmer: Yuntae Jeon
Description: GStreamer-based RTSP streaming in OOP style (rtspsrc + appsink) for multiple windows
             This version measures FPS and approximate for 5 minutes.
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import cv2
import numpy as np
import time

class RTSPStreamer:
    def __init__(self, rtsp_url, window_name):
        """
        Initialize the RTSPStreamer class for a single RTSP camera.
        
        :param rtsp_url: str, RTSP stream URL of the camera.
        :param window_name: str, Unique name for the OpenCV window.
        """
        self.rtsp_url = rtsp_url
        self.window_name = window_name
        self.pipeline = None
        Gst.init(None)
        # For FPS measurement
        self.frame_count = 0
        self.first_frame_time = None

        # Create and configure the OpenCV window once during initialization.
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 640, 480)

    def __link_elements(self, *elements):
        """
        Helper function to sequentially link multiple GStreamer elements.
        
        :param elements: list, GStreamer elements to be linked.
        :return: bool, True if linking is successful, False otherwise.
        """
        for i in range(len(elements) - 1):
            if not elements[i].link(elements[i + 1]):
                print(f"[{self.window_name}] 링크 실패: {elements[i].get_name()} -> {elements[i+1].get_name()}")
                return False
        return True

    def __create_pipeline(self):
        """
        Create and configure the GStreamer pipeline using rtspsrc and appsink.
        
        :return: bool, True if pipeline creation is successful, False otherwise.
        """
        self.pipeline = Gst.Pipeline.new(f"rtsp-pipeline-{self.window_name}")
        if not self.pipeline:
            print(f"[{self.window_name}] 파이프라인 생성 실패")
            return False

        # Create pipeline elements
        src     = Gst.ElementFactory.make("rtspsrc", "source")
        depay   = Gst.ElementFactory.make("rtph264depay", "depay")
        parse   = Gst.ElementFactory.make("h264parse", "parse")
        decoder = Gst.ElementFactory.make("avdec_h264", "decoder")
        convert = Gst.ElementFactory.make("videoconvert", "convert")
        sink    = Gst.ElementFactory.make("appsink", "sink")

        if not all([src, depay, parse, decoder, convert, sink]):
            print(f"[{self.window_name}] 요소 생성 실패")
            return False

        # Set RTSP source properties
        src.set_property("location", self.rtsp_url)
        src.set_property("latency", 500)

        # Configure appsink
        sink.set_property("emit-signals", True)
        sink.set_property("sync", False)
        # Limit buffering to reduce memory usage
        sink.set_property("max-buffers", 1)
        sink.set_property("drop", True)

        caps = Gst.Caps.from_string("video/x-raw, format=BGR")
        sink.set_property("caps", caps)
        sink.connect("new-sample", self.__on_new_sample)

        # Add elements to the pipeline
        self.pipeline.add(src)
        self.pipeline.add(depay)
        self.pipeline.add(parse)
        self.pipeline.add(decoder)
        self.pipeline.add(convert)
        self.pipeline.add(sink)

        # Connect the dynamic pad signal from rtspsrc to the depayloader
        src.connect("pad-added", self.__on_pad_added, depay)
        # rtsp 에서 동적 pad 생성 -> "pad-added 시그널 발생" (api형식) -> depay 정적 pad와 연결
        # 이후 elements들은 모두 정적 pad

        # Link static elements in sequence
        if not self.__link_elements(depay, parse, decoder, convert, sink):
            print(f"[{self.window_name}] 정적 요소 링크 실패")
            return False
        # link elements의 경우 이후 모든 요소들의 정적 input, output pad 간 자동 연결수행

        return True

    def __on_pad_added(self, src, new_pad, depay):
        """
        Callback function triggered when a new pad is added to rtspsrc.
        
        :param src: GStreamer element, the source element.
        :param new_pad: GStreamer Pad, newly created pad.
        :param depay: GStreamer element, the depayloader to link to.
        """
        print(f"[{self.window_name}] 새 패드 추가: {new_pad.get_name()}")
        sink_pad = depay.get_static_pad("sink")
        if sink_pad.is_linked():
            print(f"[{self.window_name}] 디페이로더의 sink pad가 이미 링크되어 있음")
            return

        ret = new_pad.link(sink_pad)
        if ret == Gst.PadLinkReturn.OK:
            print(f"[{self.window_name}] 패드 연결 성공")
        else:
            print(f"[{self.window_name}] 패드 연결 실패: {ret}")

    def __on_new_sample(self, sink):
        """
        Callback function triggered when a new frame sample is received from appsink.
        
        :param sink: GStreamer element, the appsink receiving the frames.
        :return: Gst.FlowReturn, Status of the sample processing.
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
                print(f"[{self.window_name}] 버퍼 매핑 실패")
                return Gst.FlowReturn.ERROR

            # Convert the raw buffer data to a numpy array for OpenCV
            frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape((height, width, 3))
            buf.unmap(map_info)
            
            # Update FPS counters
            now = time.time()
            if self.first_frame_time is None:
                self.first_frame_time = now
            self.frame_count += 1

            # Schedule frame visualization (with FPS overlay) in the GLib main loop
            GLib.idle_add(self.__visualize_frame, frame)
            return Gst.FlowReturn.OK
        return Gst.FlowReturn.ERROR

    def __visualize_frame(self, frame):
        """
        Display the processed frame in an OpenCV window with overlays.
       
        :param frame: numpy.ndarray, the image frame to display.
        :return: bool, always returns False to indicate the callback need not be re-added.
        """
        # Make a writable copy of the frame
        frame = frame.copy()

        # Calculate current average FPS (if available)
        if self.first_frame_time is not None:
            elapsed = time.time() - self.first_frame_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0.0
            cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
        # Overlay frame count and timestamp on the frame
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        cv2.putText(frame, f"{self.window_name} Frame: {self.frame_count}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.putText(frame, f"Time: {timestamp}", (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        
        # Display the frame in the already-created window
        cv2.imshow(self.window_name, frame)

        return False

    def __on_message(self, bus, message):
        """
        Handle GStreamer bus messages.
        
        :param bus: GStreamer Bus.
        :param message: GStreamer Message.
        :return: bool, True if the message was handled.
        """
        msg_type = message.type
        if msg_type == Gst.MessageType.EOS:
            print(f"[{self.window_name}] EOS 도달 - 스트림 종료")
            self.stop()
        elif msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"[{self.window_name}] 에러 발생: {err}, {debug}")
            self.stop()
        return True

    def run(self):
        """
        Start the GStreamer pipeline.
        
        :return: bool, True if the pipeline starts successfully.
        """
        if not self.__create_pipeline():
            return False

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.__on_message)

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print(f"[{self.window_name}] PLAYING 상태로 전이 실패")
            self.pipeline.set_state(Gst.State.NULL)
            return False

        return True

    def stop(self):
        """
        Stop the GStreamer pipeline.
        """
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            print(f"[{self.window_name}] 파이프라인 종료")

if __name__ == "__main__":
    # Initialize GStreamer
    Gst.init(None)

    # Create a global GLib main loop
    main_loop = GLib.MainLoop()

    # List your RTSP URLs here (one per camera)
    rtsp_urls = [
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/201',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/301',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/401',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/501',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/601',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/701',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/201',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/301',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/401',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/501',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/601',
        'rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/701',
    ]

    # Create a streamer for each RTSP URL with a unique window name
    streamers = []
    for idx, url in enumerate(rtsp_urls):
        window_name = f"RTSP Stream {idx+1}"
        streamer = RTSPStreamer(url, window_name)
        if streamer.run():
            streamers.append(streamer)
        else:
            print(f"[{window_name}] 스트리머 시작 실패")

    # Function to check for the 'q' key press (every 30 ms)
    def check_exit():
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("종료 키(q)가 입력됨 - 메인 루프 종료")
            main_loop.quit()
            return False  # Stop the timeout function.
        return True

    GLib.timeout_add(30, check_exit)

    # Function to terminate after 5 minutes (300 seconds)
    def on_timeout():
        print("5분이 경과하여 스트리밍을 종료합니다.")
        for streamer in streamers:
            if streamer.first_frame_time is not None:
                total_time = time.time() - streamer.first_frame_time
                avg_fps = streamer.frame_count / total_time if total_time > 0 else 0.0
                print(f"[{streamer.window_name}] 평균 FPS: {avg_fps:.2f} (총 프레임: {streamer.frame_count})")
            else:
                print(f"[{streamer.window_name}] 프레임을 한 번도 받지 못했습니다.")
        main_loop.quit()
        return False  # Stop the timeout callback.

    # Schedule the termination after 300 seconds (5 minutes)
    GLib.timeout_add_seconds(300, on_timeout)

    try:
        main_loop.run()
    except KeyboardInterrupt:
        print("키보드 인터럽트 감지 - 종료 중...")
    finally:
        # Stop all streamers and clean up
        for streamer in streamers:
            streamer.stop()
        cv2.destroyAllWindows()
