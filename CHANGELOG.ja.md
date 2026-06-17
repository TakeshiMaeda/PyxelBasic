# 変更履歴

## 0.1.0
- BASIC VM を Pyxel の描画・入力ループとは別スレッドで実行するように大幅変更
- インタプリタ・エディタ・テキスト画面を Pyxel 非依存モジュールに分離
- `VSYNC` を後方互換のための no-op に変更。`VSYNC LIST` のみ `FRAME BREAK: (none)` を表示
- 実行ペース調整の起動オプション `--vm-cycle-steps` / `--vm-cycle-ms` / `--debug-throttle` を追加、`--gfx-queue-size` を追加
- `INKEY$` をタイプアヘッド方式（入力済みの文字を 1 文字ずつ取り出し）に変更

## 0.0.6
- `IF ... THEN` に `ELSE` 対応を追加
- `:` 区切りによる 1 行複数文を追加
- `RESTORE 行番号` を追加
- `DATA` に定義した負数が正しく読めないバグを修正
- `DATA` 中の引用符なしテキストは明確なエラーを出すように修正
- `READ` で `A(I)` のような配列要素に代入できないバグを修正


## 0.0.5
- Pyxel 上で動く行番号方式のクラシックスタイル BASIC インタプリタ。
- フルスクリーンエディタによるその場編集（矢印キー・`Home`/`End`・挿入／上書き・
  `Backspace`/`Delete`・論理行のリフロー）。`Enter` でカーソル位置の論理行を投入。
- 制御構造：`GOTO`、`GOSUB`/`RETURN`、`IF...THEN`、`FOR...NEXT`。
- 数値・文字列の変数と多次元配列。
- 文字列・数学・乱数・入力の組み込み関数。
- 点・線のグラフィックとテキスト画面。`VSYNC` による柔軟なフレーム制御（命令単位で
  同期点を ON/OFF）。
- `DATA`/`READ`/`RESTORE`、`SAVE`/`LOAD` によるプログラムのファイル保存・読み込み。
- 起動オプション（`--load`、`--workdir`、`--run`、`--showfps`、`--version`）と
  コード化されたエラーメッセージ。
- `Ctrl+C` で実行中断、`Esc` で終了確認ダイアログ。
- 同梱サンプル（`hello`、`count`、`graph`、`stick`、`meteo`、`alltest`）とヘッドレス
  テストスイート。
