FROM ubuntu:22.04
SHELL ["/bin/bash", "-c"]

ENV HOME=/home/simulation

# Parameters
ARG VERSION=6.0.3
ARG INET_VERSION=4.5.0
ARG INET_VERSION_SHORT=4.5
ARG SIMU5G_VERSION=1.2.2
ARG INET_PATH=${HOME}/omnetpp-projects/inet${INET_VERSION_SHORT}
ARG SIMU5G_PATH=${HOME}/omnetpp-projects/simu5g

# Date and Time
ENV TZ="CET"
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime
RUN echo $TZ > /etc/timezone && rm -rf /var/lib/apt/lists/*

RUN apt-get update -y && apt-get install -y locales curl wget tar sudo git apt-utils
RUN localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8
ENV LANG=en_US.utf8

# Installing dependencies
RUN apt-get update -y && apt-get install -f -y openssh-server sudo git build-essential locales clang lld gdb bison flex perl \
    python3 python3-pip qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools nano \
    libqt5opengl5-dev libxml2-dev zlib1g-dev doxygen graphviz \
    libwebkit2gtk-4.0-37 xdg-utils mpi-default-dev\
    && useradd -ms /bin/bash simulation \                      
    && mkdir /var/run/sshd \    
    && ssh-keygen -A \
    && sed -i "s/^.*PasswordAuthentication.*$/PasswordAuthentication no/" /etc/ssh/sshd_config \
    && sed -i "s/^.*X11Forwarding.*$/X11Forwarding yes/" /etc/ssh/sshd_config \
    && grep "^X11UseLocalhost" /etc/ssh/sshd_config || echo "X11UseLocalhost no" >> /etc/ssh/sshd_config
RUN python3 -m pip install --upgrade numpy pandas matplotlib scipy seaborn posix_ipc latex

RUN localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

USER simulation
WORKDIR ${HOME}

# Download OMNeT++
RUN wget https://github.com/omnetpp/omnetpp/releases/download/omnetpp-${VERSION}/omnetpp-${VERSION}-linux-x86_64.tgz \
    && tar -xvzf omnetpp-${VERSION}-linux-x86_64.tgz
# Move the specific version in a common folder
RUN mv omnetpp-$VERSION omnetpp
# Changing CWD
WORKDIR ${HOME}/omnetpp
# Setting up OMNeT++ environment
ENV PATH=${HOME}/omnetpp/bin:$PATH
RUN echo "[ -f '$HOME/omnetpp/setenv' ] && source '$HOME/omnetpp/setenv' -f" >> ~/.profile
RUN . ./setenv && \
    ./configure WITH_OSG=no WITH_OSGEARTH=no && make -j $(nproc)
RUN rm -r doc out test samples misc config.log config.status
# Create omnet projects direcroty
WORKDIR ${HOME}/
RUN mkdir omnetpp-projects
WORKDIR ${HOME}/omnetpp-projects
# Install inet4.5
RUN wget https://github.com/inet-framework/inet/releases/download/v$INET_VERSION/inet-$INET_VERSION-src.tgz -O inet-src.tgz \
    && tar xf inet-src.tgz && rm inet-src.tgz
WORKDIR ${INET_PATH}
RUN source setenv && make makefiles && \
    make -j $(nproc) MODE=release && \
    rm -rf out
# Install simu5g
WORKDIR ${HOME}/omnetpp-projects
RUN wget https://github.com/Unipisa/Simu5G/archive/refs/tags/v${SIMU5G_VERSION}.tar.gz -O simu5g-src.tar.gz \
    && tar xf simu5g-src.tar.gz && rm simu5g-src.tar.gz
RUN mv Simu5G-${SIMU5G_VERSION} simu5g
WORKDIR ${SIMU5G_PATH}
RUN source setenv -f && make makefiles && \
    make -j $(nproc) MODE=release && \
    rm -rf out

# Clone and build my MMS simulation models
WORKDIR ${HOME}/omnetpp-projects
RUN git clone https://github.com/Dosclic98/MQTT_MMS_Medium.git
WORKDIR ${HOME}/omnetpp-projects/MQTT_MMS_Medium
RUN git submodule init
RUN git submodule update
WORKDIR ${HOME}/omnetpp-projects/MQTT_MMS_Medium
RUN opp_makemake -f --deep -DINET_IMPORT -I${INET_PATH}/src -I${SIMU5G_PATH}/src -L${INET_PATH}/src -L${SIMU5G_PATH}/src -lINET -lsimu5g -- -lstdc++fs && \
    make MODE=release all 
RUN rm MQTT_MMS_Medium && mv ./out/clang-release/MQTT_MMS_Medium .
WORKDIR ${HOME}/omnetpp-projects/MQTT_MMS_Medium/simulations
RUN chmod -R 765 aggregator.sh

# Clone dbn-sim-learning repository
WORKDIR ${HOME}
RUN git clone https://github.com/Dosclic98/dbn-sim-learning.git
WORKDIR ${HOME}/dbn-sim-learning
RUN chmod -R 765 runSimulation.sh
RUN python3 -m pip install -r requirements.txt

ENTRYPOINT ["/bin/bash"]
