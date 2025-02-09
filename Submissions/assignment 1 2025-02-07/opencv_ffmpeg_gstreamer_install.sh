
conda install -c conda-forge ffmpeg

conda install -c conda-forge gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly
conda install -c conda-forge gst-libav pygobject

conda install -c conda-forge cmake pkg-config numpy
git clone https://github.com/opencv/opencv.git
cd opencv
mkdir build && cd build

cmake -DWITH_GSTREAMER=ON \
      -DCMAKE_BUILD_TYPE=Release \
      ..

# -DCMAKE_INSTALL_PREFIX="/home/yt/anaconda3/envs/test" \
# -DCMAKE_PREFIX_PATH="/home/yt/anaconda3/envs/test" \
# -DPYTHON_EXECUTABLE="/home/yt/anaconda3/envs/test/bin/python" \
# -DPYTHON_PACKAGES_PATH="/home/yt/anaconda3/envs/test/lib/python3.12/site-packages" \
# -DWITH_FFMPEG=ON \

make -j$(nproc)
make install

python -c "import cv2; print(cv2.getBuildInformation())"

# Validation
gst-launch-1.0 rtspsrc location=rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101 latency=300 ! decodebin ! autovideosink

gst-launch-1.0 playbin uri=rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101


ffmpeg \
  -i rtsp://admin:1234567s@192.168.200.132:554/Streaming/Channels/101 \
  -t 5 \
  -c:v copy \
  -c:a aac -b:a 128k \
  output.mp4

# --no-cache-dir 

which gst-launch-1.0
which ffmpeg