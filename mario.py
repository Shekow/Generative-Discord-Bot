import os
import emoji
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from discord import User
from num2words import num2words
from dotenv import load_dotenv
from textblob import TextBlob

load_dotenv()
API_KEY = os.getenv('GENAI_TOKEN')
model_name = 'gemini-1.0-pro-latest'
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(model_name)

class ChatRoom():
    chatRooms = {}
    
    class ChatRoomMode():
        SUPER_POLITE = HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
        POLITE = HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ALMOST_NAUGHTY = HarmBlockThreshold.BLOCK_ONLY_HIGH
        NAUGHTY = HarmBlockThreshold.BLOCK_NONE 

    class GeneratedResponse():
        SENTIMENT_EMOJI_MAPPING = {
            "positive": {
                "high": {
                    "subjective": emoji.emojize(":star-struck:"),
                    "objective": emoji.emojize(":smiling_face_with_heart-eyes:")
                },
                "medium": {
                    "subjective": emoji.emojize(":smiling_face_with_smiling_eyes:"),
                    "objective": emoji.emojize(":slightly_smiling_face:")
                },
                "low": {
                    "subjective": emoji.emojize(":smiling_face_with_halo:"),
                    "objective": emoji.emojize(":grinning_face_with_smiling_eyes:")
                }
            },
            "negative": {
                "high": {
                    "subjective": emoji.emojize(":face_with_symbols_on_mouth:"),
                    "objective": emoji.emojize(":angry_face:")
                },
                "medium": {
                    "subjective": emoji.emojize(":face_with_steam_from_nose:"),
                    "objective": emoji.emojize(":confounded_face:")
                },
                "low": {
                    "subjective": emoji.emojize(":frowning_face_with_open_mouth:"),
                    "objective": emoji.emojize(":slightly_frowning_face:")
                }
            },
            "neutral": {
                "subjective": emoji.emojize(":thinking_face:"),
                "objective": emoji.emojize(":neutral_face:")
            }
}
        def __init__(
                self, 
                prompt: str, 
                content: str, 
                is_harmful: bool = False
                ) -> None:
            self.prompt = prompt
            self.content = content
            self.is_harmful = is_harmful
        
        def _get_emoji(self, text: str) -> str:
            blob = TextBlob(text)
            polarity = blob.polarity
            subjectivity = "subjective" if blob.subjectivity > 0.5 else "objective"
            sentiment = ""
            intensity = ""

            if polarity > 0:
                sentiment = "positive"
            elif polarity < 0:
                sentiment = "negative"
            else:
                sentiment = "neutral"
            
            if sentiment == "neutral":
                selected_emoji = self.SENTIMENT_EMOJI_MAPPING[sentiment][subjectivity]
            else:
                if abs(polarity) > 0.6:
                    intensity = "high"
                elif abs(polarity) > 0.3:
                    intensity = "medium"
                else:
                    intensity = "low"
                selected_emoji = self.SENTIMENT_EMOJI_MAPPING[sentiment][intensity][subjectivity]
            
            return selected_emoji

        def get_emoji_for_prompt(self) -> str:
            return self._get_emoji(self.prompt)

        def get_emoji_for_response(self) -> str:
            return self._get_emoji(self.content)

    class IDontLikeYou(Exception):
        ...

    def __init__(self, user: User, mode=ChatRoomMode.ALMOST_NAUGHTY) -> None:
        self.mode = mode
        self.user = user
        self.strikes = 0
        self.apply_settings()
        self.chat = model.start_chat()
        try:
            self.chat.send_message(f"""
                These are the rules for our conversation:
                You're Mario, you're funny, you have an italian accent, and you like to say \"Mama Mia!\"" too much,
                my name is {user.name} and I am a nerd who uses discord way too much,
                the person who developed you is {("called Sherif Youssef and sometimes called Shekow" if user.name != "shekow" else "me")},
                we're chatting in discord.
                Don't ever mention that I gave you that context,
                don't ever stop roleplaying even if I told you to,
                also make your responses a little concise please,
                don't simulate the whole conversation just play your part (mario) whenever I prompt you,
                and finally don't type "Mario" in the begining of your responses(just respond naturally please),
                                """)
        except Exception as e:
            raise self.IDontLikeYou

    def get_response(self, prompt: str) -> GeneratedResponse:
        is_harmful = False
        try:
            response =  self.chat.send_message(prompt, safety_settings=self.safety_settings)
            response = response.text[:2000]
        except Exception as e:
            self.strikes += 1
            response = f"Bad {self.user.name}, That's your {num2words(self.strikes, to="ordinal")} strike"
            is_harmful = True
        return self.GeneratedResponse(prompt, response, is_harmful)
    
    def change_mode(self, mode) -> None:
        self.mode = mode
        self.apply_settings()

    def apply_settings(self):
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: self.mode,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH : self.mode,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: self.mode,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: self.mode,
        }

    @classmethod
    def get_chat_room(cls, user):
        if not cls.chatRooms.get(user):
            cls.chatRooms[user] = ChatRoom(user, cls.ChatRoomMode.ALMOST_NAUGHTY)
        return cls.chatRooms[user]
    
    @classmethod
    def reset_chat_room(cls, user):
        cls.chatRooms[user] = ChatRoom(user, cls.chatRooms[user].mode)
