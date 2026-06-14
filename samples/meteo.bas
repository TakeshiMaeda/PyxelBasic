10 rem --- game sample ---
20 VSYNC CLEAR
30 vsync stick on
40 CLS
50 RANDOMIZE
60 x=30
70 DIM BX ( 9 ) , BY ( 9 ) , BA ( 9 )
80 FOR I = 0 TO 9
90 GOSUB 370
100 NEXT
110 rem --- main loop ---
120 FOR I = 0 TO 9
130 BYY = BY ( I )
140 BY ( I ) = BY ( I ) + BA ( I )
150 LOCATE BX ( I ) , BY ( I )
160 PRINT "*"
170 IF INT ( BY ( I ) ) = INT ( BYY ) THEN GOTO 200
180 LOCATE BX ( I ) , BYY
190 PRINT " "
200 IF BY ( I ) >= 39 THEN GOSUB 340
210 NEXT
220 st = stick(0)
250 bxx = x
260 IF ST = 4 AND X > 0 THEN X = X - 1
270 IF ST = 8 AND X < 63 THEN X = X + 1
280 locate x,39
290 print "I"
300 IF X = BXX THEN GOTO 120
310 locate bxx,39
320 print " "
330 GOTO 120
340 LOCATE BX ( I ) , 39
350 rem --- meteo set ---
360 PRINT " "
370 BX ( I ) = INT ( RND * 64 )
380 BY ( I ) = 0
390 BA ( I ) = RND
400 IF BA ( I ) < 0.2 THEN BA ( I ) = 0.2
410 IF BA ( I ) > 0.5 THEN BA ( I ) = 0.5
420 RETURN
