# Magic Mirror Maze

## Complete Game Description

**Format:** Three-player cooperative puzzle game on one shared screen  
**Audience:** Children aged 5–10  
**Input:** One camera, body tracking, and simple arm gestures  
**Status:** Game concept and proposed gameplay design

The established requirements are three children playing together, one mirror per child, a thick and forgiving light beam, and a small live camera preview that makes tracking and gesture recognition visible. The theme, progression, timing values, and dimensions below are proposed defaults that can be tuned during a future prototype.

## 1. The Game in One Paragraph

Three children become the guardians of a magical light. Each child controls one large mirror using simple arm gestures. Together, they guide a wide glowing beam through an enchanted maze and into a treasure chest, castle door, or other destination. The beam responds immediately when a mirror turns. Every completed puzzle requires all three mirrors, so the children must observe, experiment, and talk to one another. The game rewards finding the right route with generous aiming assistance, large objects, and clear visual feedback.

## 2. Core Experience

The central experience is: **three children, three mirrors, one shared solution**.

All three children play simultaneously. Each has independent control of their own mirror, and all see the same board. A child can change their mirror even when the light has not reached it yet.

The intended conversation sounds like this:

> “Keep the blue mirror there. I will turn the green one. Now the light is reaching your orange mirror!”

The game should feel magical, understandable, and satisfying. A short movement creates a clear result, and a successful route produces a celebration for the whole team.

## 3. Theme and Story

The children are **Light Guardians** helping restore a friendly enchanted kingdom. Its lanterns, gardens, bridges, and castle doors need magical light to wake up.

Each puzzle is a small scene with one clear purpose: open a treasure chest, illuminate a garden lantern, or restore a castle doorway. The first scene takes place in a peaceful forest courtyard with a golden lantern, three coloured mirrors, and a large treasure chest.

A small optional guide character introduces goals and offers hints. The story stays brief so the children spend most of their time playing.

## 4. Players and Mirror Ownership

| Player position at the start | Mirror | Persistent identity |
|---|---|---|
| Left child | Blue mirror | Number 1 and a star badge |
| Middle child | Green mirror | Number 2 and a leaf badge |
| Right child | Orange mirror | Number 3 and a sun badge |

Colours, numbers, and symbols appear consistently on the mirror, player card, camera overlay, and gesture feedback. Children can recognise their role without relying only on colour or reading.

The children remain side by side in their own comfortable spaces. Their mirrors can appear anywhere on the game board. Physical position identifies the player; it does not determine the mirror's position in the maze.

Ownership stays fixed throughout a level. If tracking becomes uncertain, the game pauses instead of silently handing one child's mirror to another. Players can exchange roles between levels through a deliberate reassignment step.

Every child has equal influence over the puzzle. The route might visit blue, green, then orange in one level and a different order in another.

## 5. Screen Layout

The game uses one large landscape play area with a compact interface around it.

| Screen region | Contents |
|---|---|
| Top bar | Game title, level name, team progress, hint and pause indicators |
| Main play area | Light source, three mirrors, broad beam, destination, and relevant obstacles |
| Short instruction area | One simple instruction or hint at a time |
| Bottom status strip | Three compact player cards and the live camera preview |
| Lower-right corner | Camera preview, tracking count, and gesture feedback |

The puzzle remains visually dominant. Decorative scenery adds depth but never hides mirrors, targets, or the light path. Player cards show the same three identities used on the board.

### Player Cards

Each card contains an avatar or icon, the player's number, their mirror colour and symbol, two large rotation arrows, and a tracking indicator. When a gesture registers, its corresponding arrow flashes once and the mirror visibly turns once.

## 6. Live Camera and Gesture Preview

A small live camera window is visible by default in the lower-right corner, inside the status area. It occupies approximately 20–25% of the screen width, with an option to enlarge it during setup or troubleshooting.

The preview shows all three children together. Each recognised player receives a matching blue, green, or orange outline and a simple body overlay showing the shoulders, elbows, wrists, and torso. The preview behaves like a mirror so movements are easy to understand.

Camera availability, player tracking, and accepted gestures are displayed separately:

| Indicator | Meaning |
|---|---|
| **Camera on** | Fresh camera frames are arriving |
| **3/3 players tracked** | All three assigned players are recognised with usable tracking |
| Coloured player outline | The game knows which player owns that mirror |
| Small hold-progress ring | A possible gesture is being held long enough to confirm |
| Flashing left or right arrow | A rotation command was accepted |
| Amber player badge | That player's tracking is temporarily uncertain |
| **Camera unavailable** | The camera feed is missing or frozen |

This distinction matters: a visible camera picture alone does not prove that gestures are being recognised. Children and parents should be able to see the complete chain from camera feed to player detection to accepted command.

The camera window stays outside the beam's route. It can be collapsed after setup while retaining compact tracking badges, then reopened from the pause menu. The intended default is a live local preview without recording.

## 7. Setup and Calibration

After initial launch and any required camera permission, the game presents three illustrated standing spaces. Children stand beside one another with enough room to raise their arms comfortably, while their upper bodies remain visible.

Each child briefly raises both arms to join. The game assigns the three identities and calibrates gesture thresholds to each child's body size. An on-screen demonstration then asks each child to try a left-arm and right-arm movement.

Calibration checks that the camera can see all three children, recognises the expected arm movement, and can distinguish a raised arm from a resting arm. It should work with comfortable arm movements rather than requiring a child to reach a fixed screen height.

Once all three are ready, a short countdown begins. Setup guidance uses pictures, spoken instructions, and visible success marks.

## 8. Gesture Controls

### During a Puzzle

| Gesture | Result |
|---|---|
| Raise the child's own left arm | Rotate that child's mirror one preset step anticlockwise |
| Raise the child's own right arm | Rotate that child's mirror one preset step clockwise |
| Lower both arms | Keep the selected angle and prepare for the next gesture |
| Raise both arms and hold | Pause the game |

Directions are taught with a mirrored demonstration and matching rotation arrows. The children are never asked to distinguish camera coordinates from their own left and right.

**One deliberate raise produces one rotation.** Keeping an arm up does not make a mirror spin repeatedly. A child lowers their arms before issuing another command. Both arms raised takes precedence over individual rotation gestures.

Suggested starting values are a roughly 0.4–0.6 second hold for rotation, a short neutral interval before another rotation, and about 1.5 seconds with both arms raised to pause. These are tuning targets, not fixed performance claims.

### Preset Angles

Mirrors snap between a small set of level-specific orientations. Beginner levels offer two useful angle choices; later levels can offer three or four. The available angles are selected so children can reason about visible routes without making fine adjustments.

A tiny wrist change should not alter a mirror. The interaction depends on broad arm poses.

### Hands-Free Menus

Menus use the same simple vocabulary: left arm moves the selection left or back, right arm moves it right or forward, and both arms confirm. The selected option is large and clearly highlighted.

Whenever a menu or readiness screen opens, existing poses are ignored until the players lower their arms. Confirmation then requires a fresh deliberate gesture. The gesture that paused the game cannot also confirm a menu choice or resume play.

As a proposed default, Player 1 navigates shared menus. Every player can pause. Starting or resuming a puzzle requires all three players to be present and ready. If the menu navigator is missing during a tracking pause, a remaining player can claim navigation with a deliberate both-arms confirmation.

Pause, hint, replay, next-level selection, and returning to the home screen must all be reachable through gestures.

## 9. Thick Beam and Forgiving Aiming

**The beam must be thick in both appearance and gameplay.** A wide glow around a narrow invisible hit line would not satisfy the intended experience.

The light has a broad, bright core and a softer decorative halo. The bright core represents the functional beam width. The halo adds atmosphere without extending the hit area unpredictably.

Suggested visual starting points for a 1920 × 1080 layout are:

| Element | Proposed size |
|---|---|
| Bright beam core | Approximately 24–32 pixels wide |
| Soft outer glow | Approximately 48–64 pixels across |
| Mirror receiving area | Approximately 100–140 pixels across |
| Destination receiving area | Approximately 120–160 pixels across |

These values scale with the display and can be enlarged through a comfort setting.

### What Counts as a Hit

When the beam's bright core visibly overlaps a mirror's marked receiving area, the mirror catches the light. The reflected beam then leaves from the mirror's centre in the direction determined by the incoming beam and the mirror's selected preset orientation. The destination works the same way: visible overlap with its large receiving area counts.

This small amount of magnetic alignment is an intentional game rule. It gives children a stable, predictable path even when the incoming beam is slightly off centre. The receiving area is visible, so success does not depend on an undisclosed hit box.

The first object reached along the beam determines what happens next. A mirror reflects it, a solid wall stops it, and the destination evaluates the win conditions. The beam remains one path; catching it does not leave a second branch continuing behind the mirror.

Level layouts provide generous clearance around walls and avoid ambiguous cases where a wide beam touches two possible receivers at essentially the same point. Decorative objects do not block light; genuine blockers have a consistent, recognisable appearance.

The challenge is choosing the correct route and mirror arrangement. Wide beams, large receivers, and snapping make execution forgiving.

## 10. Puzzle Rules and Victory

Each standard level contains one light source, exactly three player-controlled mirrors, one destination, and any clearly marked obstacles or checkpoints.

A level is solved when:

1. One continuous beam connects the source to the destination.
2. The live path reflects from all three player-owned mirrors.
3. Any required checkpoints have been visited in the indicated order.
4. No blocking object interrupts the path.
5. The arrangement remains valid briefly, with all three players still tracked.

A proposed confirmation time is about one second. A visible fill animation shows that the solution is registering. Once confirmed, the game freezes the solved arrangement before playing its celebration, so excited arm movements cannot undo the victory.

Every authored level must make all three mirrors necessary. A route that accidentally reaches the destination through only one or two mirrors cannot complete the level. Three small destination badges show which mirrors have participated in the current path.

Incorrect arrangements simply show where the light travels. There are unlimited adjustments, no loss of lives, and no compulsory countdown. A looping route produces a clear stable loop indication and remains available to adjust.

## 11. Simultaneous Cooperation

All three controls remain active together. The game never requires one player to finish their turn before another can act.

When two or three children rotate mirrors together, their accepted commands update the shared board and the light path is recalculated from the resulting arrangement. Each player receives their own command confirmation.

A mirror stays controllable even while unlit. Its angle remains visible, allowing the child to plan ahead. In the easiest difficulty, subtle route guides can show where light might arrive, helping downstream players participate before the first mirror is aligned.

The guide addresses the team and encourages discussion. Success belongs to everyone, and no child is labelled as the cause of a failed attempt.

## 12. Example: The First Spark

The first complete puzzle takes place in an enchanted courtyard.

- A golden lantern sits on the left and emits light to the right.
- The blue mirror is ahead of it in the lower-left area.
- The green mirror is above the blue mirror.
- The orange mirror is to the right of the green mirror.
- A large treasure chest sits below the orange mirror.

The blue player selects an angle that sends the beam upward. The green player redirects that arriving light to the right. The orange player sends it downward into the chest's broad receiving panel.

The mirror faces and the beam visibly agree about each reflection. Each child can make their adjustment whenever they choose; the description of the route does not impose a turn order.

When the beam reaches the chest through all three mirrors, the three destination badges illuminate, a short completion ring fills, and the chest opens. The team receives a star and a short congratulatory line.

The sample concept artwork depicts this arrangement, with the thick golden beam, three coloured player cards, and the live camera-status panel.

## 13. First Session and Game Flow

The first session introduces one idea at a time:

1. **Join:** all three children appear in their standing spaces and receive identities.
2. **Check controls:** each confirms that an arm raise moves their own mirror.
3. **See a reflection:** a short interactive demonstration shows light changing direction.
4. **Solve together:** all three enter the first complete puzzle.
5. **Celebrate:** the game recognises the shared solution and saves progress.
6. **Continue:** the team selects another level, replays, or takes a break.

Returning players can resume from saved progress after a brief tracking check. Tutorial instructions remain available from the menu.

## 14. Progression and Difficulty

A proposed initial campaign contains **24 levels across three areas**, with the count adjustable during design.

| Area | Levels | New ideas |
|---|---:|---|
| Forest Courtyard | 1–8 | Simple reflections, two-angle mirrors, broad clear paths |
| Crystal Garden | 9–16 | Additional angle choices, visible blockers, one required checkpoint |
| Lantern Castle | 17–24 | Less obvious routes, varied mirror order, ordered checkpoints |

All areas keep three players and one mirror each. Later levels change the reasoning demands while preserving the same gesture controls and broad beam.

Difficulty settings can adjust the number of angle choices, visible route guides, hint detail, and number of checkpoints. Adjustments happen between levels and must preserve a valid solution.

For mixed ages, a younger child can receive fewer angle choices and stronger visual guidance while another player handles a more demanding mirror. Every child's mirror remains necessary. These are suggested support settings, not judgements about a child's ability.

Two initial play modes are sufficient:

- **Adventure:** progress through the campaign together.
- **Replay:** choose any unlocked level and try different role assignments.

## 15. Hints and Optional AI Guide

Hints are available from the pause menu and a clearly marked hint option. They progress from a broad observation to a specific suggestion, then an optional temporary route preview.

For example:

1. “Look at where the light stops.”
2. “The green mirror needs to send light toward the orange mirror.”
3. A brief visual highlight shows the next useful connection.

Hints describe the actual current board. Using a hint does not remove the team's completion reward.

The core game can use prepared instructions and hints. An optional OpenAI-powered guide can add short story introductions, explain a checked hint in child-friendly language, and offer narration in the selected language, such as English or Urdu.

The game determines valid routes, accepted gestures, difficulty settings, and scoring. The optional guide explains that state. It does not independently decide whether an unverified arrangement is correct.

The intended API input is a compact description of the puzzle state and the relevant hint, while camera processing stays local. Essential feedback and gameplay remain available when the optional voice service is unavailable.

Narration uses short sentences and finishes the current sentence when background voices are heard. Explicit mute or stop controls remain available. If a future version adds spoken questions, listening should open after the guide finishes speaking.

## 16. Rewards and Saved Progress

Each completed level awards one shared team star. Opening a new area reveals a small visual reward, such as a restored garden, a lantern lighting up, or an unlocked costume accessory.

The default experience does not rank siblings against one another. Accuracy, exploration, and cooperation are recognised through completion and friendly feedback, with no speed requirement.

Saved local progress includes completed levels, unlocked areas, selected avatars or nicknames, language, sound settings, assistance settings, and calibration preferences. A returning session still checks that all three players are currently visible.

## 17. Tracking Loss, Pausing, and Rejoining

A brief tracking fluctuation must not become an unintended gesture. While a player's pose is uncertain, their mirror keeps its last confirmed angle and their badge turns amber.

If tracking remains unavailable for a short grace period, proposed initially at roughly 0.5–1 second, the entire puzzle pauses and preserves every mirror position. The camera preview identifies the missing player with a simple message such as “Player 2, step back into your space.”

A frozen or missing camera feed also pauses the game. The status must not remain green merely because an old image is still visible.

When the player returns, their original identity and mirror ownership are restored. All players confirm readiness before a brief resume countdown. If ownership cannot be determined confidently, a deliberate reassignment screen resolves it.

Camera errors and lost tracking never reduce the team's reward or reset their puzzle progress.

## 18. Art, Animation, and Sound

The proposed visual direction is a polished storybook fantasy with rich woodland colours, softly modelled objects, rounded interface panels, and warm golden light. The game board stays readable despite the detailed setting.

Mirrors are large, attractive objects with clearly angled reflective faces. Turning produces a short settling animation. The beam remains broad and visible throughout; glow does not obscure the actual route or the boundaries of receivers.

Accepted gestures produce a soft click or magical chime. Receivers light up when connected, and victory triggers a brief chest-opening or scene-restoration animation. Background music remains quieter than spoken instructions.

Motion, music, narration, and camera-preview visibility can be adjusted independently. Clear shapes, icons, and concise speech support children who are not yet comfortable reading.

## 19. Hardware and Design Boundaries

The target setup is the user's PC with a local 12 GB GPU, one webcam, and one large shared screen. The intended use of local processing is body tracking, gesture recognition, the puzzle simulation, and rendering. Exact performance would be established with the actual camera and GPU during a future prototype.

This document specifies the game experience. It leaves the programming language, framework, tracking model, packaging, and other implementation choices open.

The initial design covers exactly three simultaneous players, fixed mirror positions, preset rotations, a single broad beam, one destination per level, hands-free in-game navigation, local progress, and a visible camera-status panel.

Possible later additions include new visual worlds, community level packs, extra accessibility options, and more advanced optical objects. Beam splitters, continuous free-angle aiming, and moving mirrors would require separate gameplay design before inclusion.

## 20. What the Finished Experience Should Demonstrate

- Three children can play together and each reliably controls only their own mirror.
- Every normal level needs all three mirrors to complete.
- Each accepted arm raise creates one deliberate rotation with clear feedback.
- Children can lower their arms and rest without losing their selected angles.
- A visibly overlapping broad beam is caught by the matching large receiving area.
- The functional beam width matches the bright visible core.
- The live preview distinguishes camera activity, player tracking, and recognised gestures.
- Loss of tracking preserves the puzzle and makes the next step clear.
- A child can request pause, and the team can continue through gesture menus.
- The three children receive a shared completion reward with enough time to think.
- Optional narration supports play while the core game remains independent of it.
- The central experience stays understandable: turn your mirror, watch the light, talk to your teammates, and find the route together.
