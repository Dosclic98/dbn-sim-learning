#!/bin/bash
re="^[0-9]+$"


# Return number of active runs function
getNumActiveRuns () {
	echo $(( $(ps -aux | grep "../MQTT_MMS_Medium" | wc -l) - 2))
}


# Read parameters
if [ $# -ne 4 ]; then
    echo "Usage: $0 -r <number_of_runs> -b <batch_size>"
    exit 0;
fi
while getopts r:b: flag
do
    case "${flag}" in
        r) numRuns=${OPTARG};;
        b) batchSize=${OPTARG};;
		?)
      		echo "Invalid option: -${OPTARG}."
      		exit 1
      		;;
    esac
done

# Parameters validation
if  ! [[ $numRuns =~ $re ]]; then
	echo "-r parameter must be an integer"
	exit 1
fi
if  ! [[ $batchSize =~ $re ]]; then
	echo "-b parameter must be an integer"
	exit 1
fi

echo "Simulation runs started: see output in the 'logger.log' file"
echo "Running..."

source ~/omnetpp/setenv
for i in $(seq 0 $(($numRuns-1))); 
do 
	cd ~/omnetpp-projects/MQTT_MMS_Medium/simulations && ../MQTT_MMS_Medium -r $i -m -u Cmdenv -n '.:../src:../../inet4.5/examples:../../inet4.5/showcases:../../inet4.5/src:../../inet4.5/tests/validation:../../inet4.5/tests/networks:../../inet4.5/tutorials:../../simu5g/emulation:../../simu5g/simulations:../../simu5g/src' -x 'inet.common.selfdoc;inet.linklayer.configurator.gatescheduling.z3;inet.emulation;inet.showcases.visualizer.osg;inet.examples.emulation;inet.showcases.emulation;inet.transportlayer.tcp_lwip;inet.applications.voipstream;inet.visualizer.osg;inet.examples.voipstream;simu5g.simulations.LTE.cars;simu5g.simulations.NR.cars;simu5g.nodes.cars'  --image-path='../../inet4.5/images:../../simu5g/images' omnetpp_new.ini >> logger.log &
	if ! [[ $? -eq 0 ]]; then
		echo "Error running simulations: see logger.log for more info"
		exit 1
	fi
	numActiveRuns=$(getNumActiveRuns)
	while [ $numActiveRuns -ge $batchSize ]; do 
		numActiveRuns=$(getNumActiveRuns)
		sleep 0.1
	done
    echo "Started run $i"
done

# Wait for all simulations to end
echo "Waiting for all simulation runs to terminate..."
numActiveRuns=$(getNumActiveRuns)
while [ $numActiveRuns -ge 0 ]; do 
    numActiveRuns=$(getNumActiveRuns)
    sleep 0.1
    echo "$numActiveRuns runs still active..."
done

echo "Simulation runs terminated"

echo "Aggregating DBN traces..."

fileNamePrefix="dbnLogs"
cd ~/omnetpp-projects/MQTT_MMS_Medium/simulations && ./aggregator.sh -p ~/omnetpp-projects/MQTT_MMS_Medium/simulations/logs -f $fileNamePrefix -n $numRuns >> logger.log;

echo "Copying results to ~/dbn-sim-learning/results"
cp ~/omnetpp-projects/MQTT_MMS_Medium/simulations/logs/$fileNamePrefix.csv ~/dbn-sim-learning/results >> logger.log;
cd ~/dbn-sim-learning

echo "Simulation completed successfully!"