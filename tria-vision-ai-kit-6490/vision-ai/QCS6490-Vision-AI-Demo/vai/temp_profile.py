import re
import glob
import os

'''def get_cpu_gpu_mem_temps():
    thermal_zones = {}
    gpu_temp = 35
    mem_temp = 35
    max_temp = 35
    for zone_path in glob.glob("/sys/class/thermal/thermal_zone*"):
        zone_id = os.path.basename(zone_path)
        try:
            with open(os.path.join(zone_path, "type"), "r") as f_type:
                zone_type = f_type.read().strip()
            with open(os.path.join(zone_path, "temp"), "r") as f_temp:
                try:
                    # Read the temperature value
                    f_tempValue = f_temp.read()
                except:
                    f_tempValue = None
                    
                if f_tempValue:
                    # Convert temperature from millidegrees Celsius to degrees Celsius
                    temp_millicelsius = int(f_tempValue.strip())
                    temp_celsius = temp_millicelsius / 1000.0
                    thermal_zones[zone_id] = {"type": zone_type, "temperature": temp_celsius}
                    
            if re.match(r'cpu\d+-thermal', zone_type):
                max_temp = max(max_temp, temp_celsius)
            elif zone_type == 'ddr-thermal':
                mem_temp = temp_celsius
            elif zone_type == 'video-thermal':
                gpu_temp = temp_celsius

        except FileNotFoundError:
            print(f"Warning: Could not find 'type' or 'temp' file for {zone_id}")
        except ValueError:
            print(f"Warning: Could not parse temperature for {zone_id}")
        except Exception as e:
            #print(f"An error occurred with {zone_id}: {e}")
            pass
    return max_temp, gpu_temp, mem_temp'''

def get_cpu_gpu_mem_npu_temps():
    """
    Read CPU, GPU, Memory, and NPU temperatures from thermal zones.

    Returns:
        tuple: (cpu_temp, gpu_temp, mem_temp, npu_temp) in Celsius
    """
    cpu_temp = None
    gpu_temp = None
    mem_temp = None
    npu_temp = None

    try:
        # CPU temperature (averaging multiple cores for overall CPU temp)
        cpu_temps = []
        for zone in range(7, 21):  # thermal_zone7 to thermal_zone20 are CPU cores
            temp_file = f"/sys/class/thermal/thermal_zone{zone}/temp"
            try:
                with open(temp_file, 'r') as f:
                    temp_millicelsius = int(f.read().strip())
                    cpu_temps.append(temp_millicelsius / 1000.0)
            except:
                pass

        if cpu_temps:
            cpu_temp = sum(cpu_temps) / len(cpu_temps)
    except Exception as e:
        print(f"Error reading CPU temperature: {e}")

    try:
        # GPU temperature (averaging gpuss0 and gpuss1)
        gpu_temps = []
        for zone in [22, 23]:  # thermal_zone22 and thermal_zone23
            temp_file = f"/sys/class/thermal/thermal_zone{zone}/temp"
            try:
                with open(temp_file, 'r') as f:
                    temp_millicelsius = int(f.read().strip())
                    gpu_temps.append(temp_millicelsius / 1000.0)
            except:
                pass

        if gpu_temps:
            gpu_temp = sum(gpu_temps) / len(gpu_temps)
    except Exception as e:
        print(f"Error reading GPU temperature: {e}")

    try:
        # Memory/DDR temperature
        temp_file = "/sys/class/thermal/thermal_zone27/temp"
        with open(temp_file, 'r') as f:
            temp_millicelsius = int(f.read().strip())
            mem_temp = temp_millicelsius / 1000.0
    except Exception as e:
        print(f"Error reading Memory temperature: {e}")

    try:
        # NPU temperature (averaging nspss0 and nspss1)
        npu_temps = []
        for zone in [24, 25]:  # thermal_zone24 and thermal_zone25
            temp_file = f"/sys/class/thermal/thermal_zone{zone}/temp"
            try:
                with open(temp_file, 'r') as f:
                    temp_millicelsius = int(f.read().strip())
                    npu_temps.append(temp_millicelsius / 1000.0)
            except:
                pass

        if npu_temps:
            npu_temp = sum(npu_temps) / len(npu_temps)
    except Exception as e:
        print(f"Error reading NPU temperature: {e}")

    return cpu_temp, gpu_temp, mem_temp, npu_temp
