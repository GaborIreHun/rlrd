# ────────── 1. Base: Full ROS Desktop for GUI/Gazebo support ──────────
FROM osrf/ros:noetic-desktop-full

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# ────────── 2. Setup ROS environment ──────────

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-venv \
    python3-dev \
    ros-noetic-gazebo-ros \
    ros-noetic-gazebo-ros-pkgs \
    ros-noetic-ros-control \
    ros-noetic-ros-controllers \
    ros-noetic-rospy \
    ros-noetic-std-msgs \
    ros-noetic-sensor-msgs \
    ros-noetic-geometry-msgs \
    ros-noetic-turtlebot3-gazebo \
    ros-noetic-turtlebot3-description \
    ros-noetic-xacro \
    python3-defusedxml \
    python3-numpy \
    python3-scipy \
    git \
    curl \
    nano \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# ────────── 3. Python venv + Install RL project (editable) ──────────
WORKDIR /root/ws/rtrd

# Debug: Print working directory and list files before copy
RUN pwd && ls -la

# Copy with verbose output
COPY . /root/ws/rtrd/

# Debug: Verify files after copy
RUN echo "Checking copied files:" && \
    ls -la /root/ws/rtrd && \
    echo "Checking rlrd package:" && \
    ls -la /root/ws/rtrd/rlrd && \
    echo "Checking ros_bridge.py:" && \
    ls -la /root/ws/rtrd/rlrd/ros_bridge.py

RUN python3 -m venv /root/venv_rlrd --system-site-packages
ENV PATH="/root/venv_rlrd/bin:$PATH"
ENV VIRTUAL_ENV="/root/venv_rlrd"

# adding ROS dist-packages to venv site-packages so rospy is importable
RUN python3 -c "import site, os, sys; sp=site.getsitepackages()[0]; \
    open(os.path.join(sp,'ros_noetic.pth'),'w').write('/opt/ros/noetic/lib/python3/dist-packages\n')"

ENV PIP_DEFAULT_TIMEOUT=1800

RUN git config --global url."https://".insteadOf git:// && \
    pip install --upgrade pip==23.2.1 && \
    pip install "setuptools==58.2.0" "wheel==0.37.1" && \
    pip install "gym==0.19.0" "cloudpickle==1.6.0" "numpy==1.24.4" "scipy==1.10.1" "torch==2.2.2" "torchvision==0.17.2" "matplotlib==3.7.1" && \
    cd /root/ws/rtrd && pip install -e . && \
    pip install git+https://github.com/MattChanTK/gym-maze.git

# ────────── 4. Pre-set env vars for TurtleBot3, Python Path ──────────
ENV TURTLEBOT3_MODEL=burger

# ────────── 5. Entry point for interactive use ──────────
ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]
