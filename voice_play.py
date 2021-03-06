import os

from control import *
from window_capture import WindowCapture
import utils

from multiprocessing import Process, Queue
#import threading
import time
import win32api
import winsound
import numpy as np
import cv2
import argparse

#监听是否有语音指令
def voice_listener(speech_queue, stop_queue):
    from voice import SpeechRecognizer, StreamPatcher
    model_speech = SpeechRecognizer()

    # test and init
    text = model_speech.test_file('data/voice_test.wav')
    print('test voice:', text)

    print('voice listener start')

    with StreamPatcher() as sp:
        winsound.Beep(500, 500)
        while True:
            if stop_queue.qsize()>0:
                break
            for _ in iter(sp):
                pass

            text = model_speech.next(sp.rec_data.tobytes())
            speech_queue.put(text)

def img_saver(img_queue, stop_queue):
    while True:
        if stop_queue.qsize()>0:
            break
        if img_queue.qsize()<=0:
            time.sleep(0.05)
            continue

        data=img_queue.get()
        cv2.imwrite(f'vis/{data[0]}.jpg', data[1])

class VoicePlayer:
    def __init__(self, args):
        self.args=args
        self.pred_imsize = (1280, 720)

        self.model_tracker = TrackerInterface()
        self.model_vlm = XVLMInterface()

        self.controller = FollowController(self.pred_imsize)
        self.attacker = ScriptAttacker('control/script')
        self.capture = WindowCapture('原神')

        self.test()

    def test(self): # test and init
        img = cv2.imread('data/vlm_test.jpg')
        bbox = self.model_vlm.predict(img, '右上的盗宝团')
        print('test vlm:', bbox)

        self.model_tracker.reset(bbox)
        for _ in range(5):
            bbox = self.model_tracker.predict(img)[:4]
        print('test tracker:', bbox)

    def text_proc(self, text:str):
        part=text.split('攻击')
        if len(part)==1:
            return part
        cmd, enemy = part
        pidx=cmd.find('战术')
        plan = utils.trans_ch_int(cmd[pidx+2:]) if pidx!=-1 else 1
        return {'plan':plan-1, 'enemy':enemy}

    def start(self, vis=False):
        speech_queue=Queue(maxsize=100)
        stop_queue=Queue(maxsize=2)
        Process(target=voice_listener, args=(speech_queue, stop_queue)).start()

        if vis:
            os.makedirs('vis', exist_ok=True)
            img_queue = Queue(maxsize=100)
            Process(target=img_saver, args=(img_queue, stop_queue)).start()

        while True:
            if win32api.GetKeyState(ord('P')) < 0:
                stop_queue.put(True)
                return

            if speech_queue.qsize()<=0:
                time.sleep(0.1)
                continue

            text = speech_queue.get()
            print(text)
            text_dict = self.text_proc(text)
            if len(text_dict)==1:
                continue

            img = self.capture.cap(resize=self.pred_imsize)
            enemy = text_dict['enemy']
            recoder.write(f'{int(time.time()*1000)-time_start}, {text}\n')
            bbox = self.model_vlm.predict(img, enemy)

            self.model_tracker.reset(bbox)

            while speech_queue.qsize()<=0: #没有新指令就一直追踪当前指令
                if win32api.GetKeyState(ord('P')) < 0:
                    stop_queue.put(True)
                    return

                if vis:
                    canvas = np.copy(img)
                    cv2.rectangle(canvas, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (0, 255, 0), 2)
                    t = int(time.time() * 1000)
                    img_queue.put([t, canvas])

                if self.controller.step(bbox, enemy): #追踪目标执行完毕
                    recoder.write(f'{int(time.time()*1000)-time_start}, track over\n')
                    self.attacker.attack(text_dict['plan']) #按预设进行攻击
                    break

                img = self.capture.cap(resize=self.pred_imsize)
                bbox=self.model_tracker.predict(img)[:4]

def make_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vis", type=bool, default=False)
    return parser.parse_args()

if __name__ == '__main__':
    #从外面import这些wenet会报错
    from mmtracking.Interface import TrackerInterface
    #from voice import SpeechRecognizer, StreamPatcher
    from xvlm.Interface import XVLMInterface

    args = make_args()
    player = VoicePlayer(args)

    print('press t to start')
    winsound.Beep(700, 500)
    time_start=int(time.time()*1000)
    recoder=open('log.txt', 'w', encoding='utf8')
    while win32api.GetKeyState(ord('T')) >= 0:
        pass
    player.start(args.vis)