# Rivenvale Workshop Discord Server
Join the server to grade your Rivens. All instructions, including how to use the bot, are available in the Discord channels.  

## 🌟 Invite Link

```
discord.gg/Jgc3WnEQhq
```

**Notice:** Hosting of the Rivenvale bot on Discord may be discontinued in the future. If you’d like to continue using Rivenvale’s grading system, instructions are provided below on how to host it yourself. Please read and understand the **Usage Restrictions** before proceeding.

# Deploying Rivenvale on Your Device
## 🔒 Usage Restrictions

- You may clone and deploy the Rivenvale repository for **personal use only**.
- **Commercial use is strictly prohibited.**
- You may modify the code for personal use, but you must not change the **Rivenvale logo** or name when setting up the bot. The logo is provided in the repository as `Rivenvale_logo.png`.
- If you build your own bot using Rivenvale’s code as reference, you must use a unique logo and name to give your bot its own identity. You may not reuse Rivenvale’s proprietary assets, such as `bg.png`, `best.pt`, or any other files included in the repository.

## 📥 Cloning the Repository

To get started, clone the repository to your device:

1. **Check Git Installation**  
Make sure Git is installed. You can download it from [git-scm.com](https://git-scm.com/downloads) or verify with:

```
git --version
```

2. **Clone the Repository**  
Navigate to the directory where you want to install the bot, then run:

```
git clone https://github.com/ExerentPrime/Rivenvale.git
```

3. **Verify Files**  
Confirm that `bot.py` and other asset files are present:

```
ls
```

## 🔧 Environment Setup

You’ll need a `.env` file to store your **Discord bot token** and **OCR API key**.

1. **Get a Discord Bot Token**
   - Create an application and bot in the [Discord Developer Portal](https://discord.com/developers/applications).  
   - Copy your bot token.

2. **Get an OCR API Key**
   - Visit [OCR.Space](https://ocr.space/ocrapi/freekey).  
   - Register for a free key, or purchase a PRO plan for higher limits.

3. **Create the .env File**  
Inside your project folder, create a file named `.env` and add your keys:

```
DISCORD_BOT_TOKEN=AAAa99A99AA9A9Aaa99AAA9A999Aa.aAAaaA.AAAAaAaAAA_aaaaa99999AaAaAaAAaa
OCR_API=K99999999999999
```

## 📋 Requirements

### System Requirements
- **Python**: 3.8 or higher (tested on 3.12.3). Download from [python.org](https://www.python.org/downloads/).
- **OS**: Windows, macOS, or Linux (must support image processing libraries like OpenCV).

### Python Dependencies
Install required packages with:

```
pip install aiohttp discord.py Pillow requests pandas python-dotenv ultralytics opencv-python numpy
```

## 🚀 Running the Bot
1. Clone the repository.  
2. Install dependencies.  
3. Create and configure your `.env` file.  
4. Ensure all asset files are in the project directory.  
5. Start the bot:

```
python bot.py
```

## 🔄 Updating and Maintenance

Rivenvale is updated regularly with new Warframe patches. To keep your bot working correctly, update the code and refresh certain data files:

### Update the Code
Pull the latest changes:

```
git pull origin main
```

### Refresh Data Files
The bot downloads `roll_data.xlsx` and `weapon_data.txt` on first run. After a Warframe patch, delete these files and restart the bot to refresh:

```
rm roll_data.xlsx weapon_data.txt
```
