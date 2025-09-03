## 📥 Cloning the Repository

To get started with Rivenvale, clone the repository from GitHub to your local machine using the following steps:

1. **Ensure Git is Installed**  
   Make sure you have Git installed. You can download it from [git-scm.com](https://git-scm.com/downloads) or verify by running:
```
git --version
```
2. **Clone the Repository**  
After navigate to the Project Directory, run the following command in your terminal or command prompt to clone the Rivenvale repository:
```
git clone https://github.com/ExerentPrime/Rivenvale.git
```
3. **Verify Cloned Files**  
Check that the repository contents, including `bot.py` and other asset files, are present:
```
ls
```

## 🔧 Environment Setup

You’ll need a `.env` file to store your **Discord bot token** and **OCR API key**.

1. **Get a Discord Bot Token**
- Create a Discord application and bot via the [Discord Developer Portal](https://discord.com/developers/applications).  
- Copy your bot token. (You can also Google for tutorials or ask an AI assistant like ChatGPT/Copilot for guidance.)

2. **Get an OCR API Key**
- Go to [OCR.Space](https://ocr.space/ocrapi/freekey).  
- Register for a **free key** or purchase a **PRO plan** if you need higher limits.

3. **Create the .env File**
- Inside your project root, create a file named `.env` and paste Discord bot token and OCR API key. The file should look like this:
```
DISCORD_BOT_TOKEN=AAAa99A99AA9A9Aaa99AAA9A999Aa.aAAaaA.AAAAaAaAAA_aaaaa99999AaAaAaAAaa
OCR_API=K99999999999999
```
## 📋 Requirements

To run the bot, ensure you have the following:

### System Requirements
- **Python**: Version 3.8 or higher (tested on 3.12.3). Download from [python.org](https://www.python.org/downloads/).
- **Operating System**: Windows, macOS, or Linux (with support for image processing libraries like OpenCV).

### Python Dependencies
Install the required Python packages using pip.

- **Installation Command**:
```
pip install aiohttp discord.py Pillow requests pandas python-dotenv ultralytics opencv-python numpy
```

## 🚀 Running the Bot
1. Install dependencies as above.
2. Set up your `.env` file.
3. Ensure required asset files in the project directory.
4. Run the bot:
```
python bot.py
```
