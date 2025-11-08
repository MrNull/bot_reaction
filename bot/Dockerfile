FROM python:3.11-slim

WORKDIR /bot_reaction
COPY . /bot_reaction

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]
