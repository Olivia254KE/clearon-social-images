# Clearon quality review rubric

Used in the QUALITY GATE of every autopilot run, after `tools/qa_check.py` and `tools/qa_dom.js` pass
and before anything is pushed or scheduled. The reviewer is a separate agent that did not make the
content. It looks at each image at full size AND at phone size (the review sheet shows both), at
the video frame sheets, and reads the captions.

Score every item 1-5. **An asset passes only if every item scores 4 or 5 and no hard fail applies.**
Anything below 4 comes back with a specific, actionable fix ("headline wraps to 4 lines: cut to
'BOOK BEFORE THE RUSH'"), not a vague one ("improve hierarchy").

## A. Stopping power and message (the 1-second test)
1. **Hook**: at phone size, can you tell in about one second what the post is about and why an importer should care? The headline is a benefit, a question or a tension, not a label.
2. **One idea**: the image makes one point. Cards have one message; posters have one headline plus supporting detail.
3. **Hierarchy**: a clear reading order: headline, then visual, then detail, then CTA. One dominant element; nothing competes with the headline.
4. **Copy**: headline 2 to 8 words; body lines short; no jargon left unexplained; no spelling or grammar errors; Kenyan importer language (Mombasa, JKIA, KRA, supplier, quote); British spelling (itemised, organise).

## B. Visual design
5. **Legibility at phone size**: every word readable in the 360px preview; body text effectively 20px+ at 1080 wide; strong contrast (WCAG AA 4.5:1 for body text, 3:1 for big headlines); no text on busy backgrounds without a panel.
6. **Layout and spacing**: consistent outer margins (about 56px), elements aligned to a grid, even gaps, balanced composition; no cramped corners, no large dead areas that look unfinished, nothing touching or crossing the edges.
7. **Brand**: only brand colours (navy #002244, deep navy #001a35, teal #00b9ab, blue #3079ff, white, plus tints); Anton for headlines, Poppins for body; correct logo version (white on dark, colour on light) in a top corner about 120px wide, never stretched, recoloured or crowded; the footer has the phone with WhatsApp icon and the email.
8. **Craft**: the illustration or graphic is clean and intentional (no misaligned shapes, stray lines, icons sitting oddly, mismatched stroke weights); no pixelation, banding or JPEG artefacts; it looks like a professional agency made it.
9. **Freshness**: visibly different from the last seven days of posters and cards (layout, background, central graphic), and from the other assets in today's set.

## C. Carousels (in addition)
10. **Swipe flow**: slide 1 is a strong hook with a swipe cue; one point per slide; slide counter and progress line correct on every slide (2/6, 3/6 …); the same visual system throughout; the last slide is the WhatsApp CTA with the number large.
11. **Consistency**: the logo, footer, margins and type sizes stay identical from slide to slide; nothing jumps position between slides.

## D. Videos (from the frame sheet, every 0.5 s)
12. **Opening and cover**: the first frame is branded (never black); the cover frame shows the poster fully.
13. **Pacing and transitions**: each slide holds about 6 s or more; transitions are smooth; no frame shows two slides' text on top of each other, a flash, a black gap or a half-drawn frame.
14. **Ending and sound**: the end card shows "Chat with us on WhatsApp" with the number; the music mood suits the topic; sound is not silent and not clipping (qa_check measures this).

## E. Captions (per platform)
15. **Opening line**: the first line hooks (the feed cuts captions after 1 to 2 lines); emoji used sparingly and purposefully.
16. **CTA**: one clear, specific ask (what to send, and that WhatsApp is the way); cards end with a question that invites comments; carousels invite swipe and save.
17. **Platform fit**: LinkedIn professional and fuller; Facebook friendly; X tight; IG/TikTok say "link in bio"; Threads ≤500 characters. Contact line present; UTM links correct (qa_check verifies).

## Hard fails (any one means redo, whatever the scores)
- Any fact, figure, date, fee, transit time or rule that is not from a Clearon article read this run or from the stable facts the task allows; any invented statistic, testimonial or client result; an example scenario presented as a real client.
- Wrong or missing phone number, email or WhatsApp link.
- Text clipped, overlapping, off the canvas or over the logo; a blank, black or broken frame in a video.
- Another company's logo or branding, a real person's face, copyrighted music or imagery.
- An image that looks amateur next to a professional logistics brand's feed.

## Verdict format (reviewer returns this, one line per asset)
`PASS <file>` or `FIX <file>: <item numbers> – <specific fix>`; then a 1-line overall note on how the set works as a feed (variety, colour balance, nothing two-in-a-row look-alike).
