# File Path Manager
# import os
# sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import socket
import sys
import traceback

from adapt.intent import IntentBuilder
from mycroft import MycroftSkill, intent_handler
from mycroft.util.log import LOG

from .code.message.vqa_message import VqaMessage
from .code.misc.camera import Camera
from .code.misc.receiver import Receiver
from .code.misc.sender import Sender
from .code.misc.text_normalizer import to_uniform
from .default_config import DefaultConfig

# TODO: Make sure "." before module name is not missing

LOG.warning('Running Skill Question Answering On Python ' + sys.version)

try:
    import picamera
except ImportError:
    # re-install yourself
    from msm import MycroftSkillsManager

    msm = MycroftSkillsManager()
    msm.install("https://github.com/ITE-5th/skill-question-answering")


class QuestionAnsweringSkill(MycroftSkill):
    def __init__(self):
        super(QuestionAnsweringSkill, self).__init__("QuestionAnsweringSkill")
        LOG.warning('Running Skill Question Answering ')

        # if "server_url" not in self.settings:
        #     self.settings["server_url"] = "192.168.43.243"
        self.socket = None
        self.receiver = None
        self.sender = None
        self.port = None
        self.host = None
        self.camera = Camera(width=800, height=600)
        self.connect()

    def connect(self):
        try:
            self.port = DefaultConfig.QUESTION_ANSWERING_PORT
            self.host = self.settings.get("server_url", DefaultConfig.server_url)
            LOG.info("Question Answering Skill started " + self.host + ":" + str(self.port))
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.receiver = Receiver(self.socket, json=True)
            self.sender = Sender(self.socket, json=True)
            LOG.info('connected to server:' + self.host + ' : ' + str(self.port))
        except Exception as e:
            LOG.warning(str(e))

    def ensure_send(self, msg):
        retries = 3
        while retries > 0:
            try:
                retries -= 1
                self.sender.send(msg)
                break
            except Exception as e:
                if retries <= 0:
                    LOG.warning('Cannot Connect')
                    return False
                self.connect()
                LOG.warning(str(e))
        return True

    @intent_handler(IntentBuilder("VqaIntent").require('question').require('question_words'))
    def answer(self, message):
        try:
            image, _ = self.camera.take_image()
            utterance = message.data.get('utterance')
            question = to_uniform(''.join(utterance.split('question')))
            msg = VqaMessage(image=image, question=question)
            LOG.info('sending question : ' + question)

            sent = self.ensure_send(msg)
            if not sent:
                self.speak_dialog('ConnectionError')
                return False

            response = self.receiver.receive()
            LOG.info(response)
            result = self.handle_message(response.get('result'))
            self.speak_dialog("Result", result)

        except Exception as e:
            LOG.info('Something is wrong')
            LOG.info(str(e))
            LOG.info(str(traceback.format_exc()))
            self.speak_dialog("UnknownError")
            self.connect()
            return False
        return True

    @staticmethod
    def handle_message(response):
        """
        converts server response to meaningful sentence
        :param response: string of answers
        :return: dictionary contains sentence in result
        """
        phrase = ''
        if response.strip() != '':
            answers = response.split(',')
            answers_count = len(answers)
            for i in range(answers_count):
                answer = answers[i].strip().capitalize()
                phrase += answer + (
                    ' . or ' if i == answers_count - 2 and answers_count > 1 else ' . ')
                if any(char.isdigit() for char in answer) or answer in ('Yes', 'No'):
                    break
        return {'result': phrase}

    def stop(self):
        super(QuestionAnsweringSkill, self).shutdown()
        LOG.info("Question Answering Skill CLOSED")
        self.socket.close()


def create_skill():
    return QuestionAnsweringSkill()
