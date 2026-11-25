# Play Together: Magic Mirror Maze and Friends

A collection of gentle cooperative games for three children. Amna, Maryam and Abdullah play as a team; there are no individual scores or eliminations.

## Start playing

From this folder, run:

```bash
./run.sh
```

Use `./run.sh --fullscreen` for a full screen, or `./run.sh --camera 10` to choose a particular `/dev/video10`. The game normally finds the USB camera automatically and requests 1920×1080 video. Pose tracking tries the GPU first and falls back to CPU if needed.

Use `./run.sh --fullscreen --arabic` to open the Arabic tutor directly, or use the **Arabic Pictures** desktop launcher.

At the home screen choose **Bear Adventure**, **More Games**, or the original **Mirror Maze**. The highlighted choice moves through the menu; lower an arm and then hold it up for about two seconds to choose. The same gesture continues after a celebration. A mouse can also select any button.

For the cooperative activities, stand in front of the camera in this order, with a little space between everyone:

- Left: **Amna**, blue.
- Middle: **Maryam**, green.
- Right: **Abdullah**, orange.

Wait until all three are recognized and colored. When a child's turn is highlighted, that child raises one arm. Lower the arm before raising it again. In the bear adventure, each child opens their own gate in turn; one gate opens at a time. Everyone earns shared stars. Some levels change the order of turns.

## Games

- **Bear Adventure:** help the bear return home through three gates. Twelve easy levels.
- **Magic Garden, Feed the Dragon, Build a Rainbow, Wake the Castle, Music Together:** take turns to make something happen together. Twelve rounds of each, with the same easy controls and different turn orders.
- **Word Garden:** say an English word beginning with the letter shown, and grow the garden. Twelve letter rounds, A–L.
- **Build a Village:** say English words to add houses. Six rounds.
- **Animal Rescue:** say **cat**, **bird**, or **rabbit** to welcome the animals. Six rounds.
- **Story Builder:** take turns saying English words to make a short, silly story. Six rounds.
- **Cities & Countries:** name a place beginning with the letter. Six rounds; the game accepts the examples shown and many other country and city names from the computer's local lists. The city list is not exhaustive.
- **Arabic Pictures:** a live voice tutor welcomes Urdu-speaking children in Urdu, asks their names, then asks **آسان یا مشکل؟**. It uses Arabic questions and vocabulary with occasional English encouragement. One to three children take turns with 100 pictures shown in a shuffled order. The tutor asks **ما هذا؟** or **ما هذه؟** without showing or saying the answer first. In easy mode, the child can say the word; in hard mode, the tutor asks for the full phrase. One correct answer is enough. The tutor can model the word after an incorrect answer or when asked for help. For example, answer **ما هذا؟** with **هذا كتاب** or **ما هذه؟** with **هذه مروحة**. The word list is in [ARABIC_VOCABULARY.md](ARABIC_VOCABULARY.md).
- **Magic Mirror Maze:** the original six cooperative mirror puzzles.

Progress is saved on this computer. Rounds repeat their simple mechanics with new letters, words, or turn orders; they do not become progressively difficult.

## Speaking games

In the English speaking games, the screen announces whose turn it is. Raise an arm, wait for **LISTENING**, then say the answer clearly. You can also click **Speak**. If the answer is missed, use **Hear a hint** and try again. There is no penalty for retries. In Arabic Pictures, no clicks or gestures are needed after opening the activity: listen to the tutor and speak when it has finished.

The English speaking games process audio locally with the existing Faster Whisper model on the NVIDIA GPU. **Arabic Pictures is different:** it streams microphone audio to OpenAI's Realtime API while that activity is open and needs an internet connection and an API key; API usage is billed by OpenAI. The tutor produces AI-generated speech, speaks Urdu with Arabic and some English, and manages the pictures through game tools. It pauses listening while it speaks to reduce speaker echo, so speak after it finishes. Say “home” to leave. The camera is not used while Arabic Pictures is open; when entering from a camera game, it is released. A single microphone cannot identify which child spoke, so the children take turns by agreement. Recognition and pronunciation can vary; check Arabic with a fluent speaker.

To configure the key for the desktop launcher, use a terminal and enter the key at the hidden prompt:

```bash
cd ~/Documents/magic-mirror-maze
umask 077
read -rsp 'OpenAI API key: ' task_api_key; echo
printf 'export OPENAI_API_KEY=%q\n' "$task_api_key" > .env
unset task_api_key
```

The key is saved locally in `.env`, with owner-only permissions. That file is ignored by Git. Restart the game after adding the key. The default live model is `gpt-realtime-2.1-mini`; `OPENAI_REALTIME_MODEL` can select another compatible Realtime model.

The live tutor's editable word data is in `magic_mirror/arabic_vocabulary.json`. Each entry names its local `assets/vocab_<picture>.png`, Arabic word, pronunciation, English meaning, and grammatical gender (`m` or `f`). Add a matching image when adding a word. Common alternate answers are defined in `magic_mirror/arabic_catalog.py`.

The local, ignored `config.json` contains the children's displayed names and the machine-specific paths to the existing local speech Python environment, model, and cuDNN library. If the local model is moved or removed, update those paths. A missing model or microphone is reported on screen; the other games remain available. Audio and transcriptions are not saved by the game.

## Other controls

Click **Sound on/off** or press **M** to mute or unmute. **P** or **Esc** pauses; **F11** toggles fullscreen. The mirror game uses these optional keys:

| Player | Left arm | Right arm |
| --- | --- | --- |
| Amna, blue | A | D |
| Maryam, green | F | H |
| Abdullah, orange | J | L |

In the mirror game, raise your left or right arm to turn your mirror. Hold both arms up briefly to pause. If everyone leaves the camera, play pauses after a short grace period. **P** resumes in keyboard mode if necessary. The webcam preview shows assigned children in blue, green, and orange; gray indicates someone has not yet been assigned.

`./run.sh` creates `.venv`, installs the application packages, and downloads the pose model into `models/` on first setup. The separate local speech environment and model are already configured on this computer. Sound credits are in [assets/sounds/SOURCES.md](assets/sounds/SOURCES.md).
