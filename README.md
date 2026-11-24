# Magic Mirror Maze

Three children, three mirrors, one beam of light. The camera, the body tracking, and the window all run on this computer.

The full design is in [Magic_Mirror_Maze_Game_Description.md](Magic_Mirror_Maze_Game_Description.md). This build is the forest courtyard: six levels, two mirror faces, and a thick beam.

```bash
./run.sh
./run.sh --camera 10
./run.sh --fullscreen
```

`--camera 10` reads `/dev/video10`. Use `--camera 0` for the first local webcam. Keys work even when the camera cannot see anyone.

Stand left, middle, and right. Raise your own left arm to turn your mirror one way, and your own right arm to turn it the other way. One raise turns it once. Hold both arms up for a moment to pause. Lower them to continue.

| Player | Left | Right |
| --- | --- | --- |
| 1 Blue, star | A | D |
| 2 Green, leaf | F | H |
| 3 Orange, sun | J | L |

These first levels have two faces. Either arm switches to the other face. `/` sends light one way. `\` sends it the other way. Every level needs all three mirrors before the chest will open.

`H` shows the next hint. `P` or `Esc` pauses. `F11` fills the screen. From the pause card you can resume, ask for a hint, restart, or go home.

| Level | Name |
| --- | --- |
| 1 | The First Spark |
| 2 | The Low Road |
| 3 | The Side Gate |
| 4 | The Way Home |
| 5 | Mind the Stones |
| 6 | The Long Bend |

Clear a level to open the next one. Stars are saved in `progress.json` on this computer. That file is not part of the git repo.

`./run.sh` creates `.venv`, installs the Python packages, and downloads the pose model into `models/` the first time. The game still runs from the keyboard if the model or the camera is missing.
