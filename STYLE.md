# The OpenSlop show bible

Read this before you write a scene. It is what keeps a movie written by
strangers looking like one movie, and what makes a prompt come out as a scene
instead of a slideshow.

## The look

Flat 2D cel animation. Thick black outlines, flat fills, no gradients. A cool
palette of briny blues and fog greys, warmed at golden hour by sunset oranges
and lamp-yellow. Staged, storybook compositions: a clear subject, a clear
background, room to read the shot at a glance.

Every prompt names this look in full. The shortest form that works is
`Flat 2D cel animation, thick black outlines, flat fills.` followed by the
palette the scene uses.

## The world

A small fog-bound harbour town under a single turning lighthouse. The sea is
always near. Weather does a lot of the acting: fog, rain on glass, a low sun.
Nights are deep blue, never true black.

## The cast so far

Describe a character the same way every time they appear. The model has never
seen them before.

- **The keeper**: an old man with a salt-white beard, deep lines around his
  eyes, a dark wool cap, and a heavy blue coat. Tired and kind. His voice is
  low, gravelly, and slow. He talks to the light as if it listens.
- **The green light**: a single small green light on the water where no boat
  should be. It blinks in threes, like a code. It is not friendly and not
  hostile yet.
- **The town**: a handful of low stone houses, moored fishing boats, a leaning
  wooden water tower. Mostly empty; the town is a mood, not a crowd.
- **The thing under the water**: never shown. Only what it does to the sea: a
  long slow swell where no wave should be, a dark mass moving beneath the
  surface too big to see the edges of, boats rocking, mooring ropes straining.
  Do not give it a shape, a face, or a name until a scene earns the reveal.

Add to the cast in a new episode. Once a character lands, describe them the
same way in every later scene, and add them here in a pull request so the next
writer can.

## The one rule the model forces

The video model reads **only the scene you are writing**, never the scenes
around it. So every scene must re-describe the whole picture from scratch: the
look above, the setting, who is in frame, the light, the mood, the sound.
Anything you leave out will vanish or mutate. This feels repetitive in the file
and reads as one continuous movie on screen. That is the trade, and it is not
optional.

## How to write a prompt

A prompt is 200 to 800 characters of plain prose (the checker counts). Aim for
500 to 700: enough to carry everything below, with room to spare. Write it in
this order, which is the order the model weighs it:

1. **The shot and the subject.** What kind of shot (wide, medium, close-up,
   extreme close-up), and who or what is in it, described in full.
2. **The action.** One thing happening. A scene is a few seconds; one clear
   movement reads, three do not.
3. **The setting.** Where this is, in enough detail to be drawn.
4. **The camera.** Holding still, drifting forward, slowly pushing in. Say it
   plainly; the model cannot read film jargon.
5. **The look and the light.** The house look above, then the palette this
   scene uses and where the light comes from.
6. **The mood.** Two or three words.
7. **The sound.** Always last, always present. See below.

Strong nouns and verbs over piles of adjectives. Describe only what the camera
sees and the microphone hears: no text on screen, no titles, no scene numbers,
no "cut to", no "as before" or "the same as the last scene". Use plain
punctuation; commas, full stops, and colons.

## Sound

The model renders sound with the picture, and it renders **speech**. A prompt
that says nothing about sound comes out flat or with a noise it invented. So:

- End every prompt with a soundscape clause: the ambience, the effects, the
  mood of any music. `Sound: low surf, a buoy bell far off, a faint electric
  hum.` Three or four sounds is plenty.
- When someone speaks, write **who speaks**, the **exact words in quotes**, and
  **how the voice sounds**: `He speaks slowly in a low, tired, gravelly voice:
  "They only come when the light is wrong."` The model says the words you
  give it; if you only write "he mutters something", it will invent the
  something.
- One line of dialogue per scene is the sweet spot. A speech does not fit in
  ten seconds, and the clip ends when the time is up, mid-sentence if it must.
- Silence is a sound too. `No gulls, no bell.` tells the model what to leave
  out.

## Length

`seconds` runs from about 5 to 14; the model rounds it up to the nearest
length it can make (see the writing guide). Use the short end, under 8 seconds, only for a transition, an
establishing shot, or a reaction beat. A scene that carries a line of dialogue
or an action needs 8 seconds or more.

## Tone

Gentle, a little eerie, a little funny. Small stakes told seriously. Think a
bedtime story that is not quite sure it is safe.
