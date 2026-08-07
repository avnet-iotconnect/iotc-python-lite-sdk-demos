import xarm
import traceback

print('start')
try:
    arm = xarm.Controller('USB')
    print('created', arm)
    try:
        v = arm.getBatteryVoltage()
        print('volt', v)
    except Exception as e:
        print('getBattery error', e)
        traceback.print_exc()
except BaseException as e:
    print('exc', e)
    traceback.print_exc()
finally:
    try:
        arm.servoOff()
        print('servos off')
    except:
        pass
