10 REM ============================================
20 REM  SOUND DEMO (PLAY)
30 REM  Z = play a sound effect (interrupts the BGM
40 REM      on channel 1, then the BGM resumes)
50 REM  X = stop all sound
60 REM  C = restart the BGM
70 REM ============================================
80 CLS
90 PRINT "SOUND DEMO"
100 PRINT "=========="
110 PRINT "Z = SOUND EFFECT"
120 PRINT "X = STOP"
130 PRINT "C = RESTART BGM"
140 PRINT
150 REM --- start a 2-channel looping BGM ---
155 BGM0$ = "T120 O2 L8 C E G E C E G E" : BGM1$ = "T120 O3 L4 C G C G" : BGM2$ = "t120 l8 o4 e2r4ed c2cdcd e2r4ed c2cdcd"
160 PLAY LOOP BGM0$,BGM1$,BGM2$
170 REM ====== main loop ======
180 LOCATE 0,8
190 IF PLAY(0) THEN PRINT "BGM   : ON " : GOTO 210
200 PRINT "BGM   : OFF"
210 LOCATE 0,9
220 IF PLAY(1) THEN PRINT "CH1   : BUSY" : GOTO 240
230 PRINT "CH1   : ---- "
240 REM --- Z: sound effect interrupts channel 1 ---
250 IF BUTTON(0) THEN PLAY CH 1,"T160 O4 L16 C E G > C"
260 REM --- X: stop everything ---
270 IF BUTTON(1) THEN PLAY STOP
280 REM --- C: restart the BGM ---
290 IF BUTTON(2) THEN PLAY LOOP BGM0$,BGM1$,BGM2$
300 VSYNC
310 GOTO 180
