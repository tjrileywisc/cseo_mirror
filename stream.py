# import required libraries
from vidgear.gears import CamGear
import cv2
from ffpyplayer.player import MediaPlayer

# open any valid video stream(for e.g `myvideo.avi` file)
wcac_path="https://telvuevod-secure.akamaized.net/vodhls/vod_player/249/media/856528/1708567600/master.m3u8"
stream = CamGear(source=wcac_path).start()
player = MediaPlayer(wcac_path)
# loop over
while True:

    # read frames from stream
    frame = stream.read()
    audio_frame, val = player.get_frame()

    # check for frame if Nonetype
    if frame is None:
        break

    # {do something with the frame here}

    # Show output window
    cv2.imshow("Output", frame)

    # check for 'q' key if pressed
    #The waitKey() is looking for milliseconds. We'll get that tied to framerate eventually
    key = cv2.waitKey(30) & 0xFF
    if key == ord("q"):
        break
    
    if val != 'eof' and audio_frame is not None:
        img, t = audio_frame

# close output window
cv2.destroyAllWindows()

# safely close video stream
stream.stop()
