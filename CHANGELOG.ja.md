# 変更履歴

## 0.1.2
- `CLS` に引数を追加
- `LIST` の範囲に行番号なし指定ができるように：`LIST -100`、`LIST 200-`
- 矩形・塗りつぶし矩形を描く `LINEB` / `LINEBF` を追加
- 座標の色を返す `POINT(x, y)` 関数を追加
- 楕円・塗りつぶし楕円を描く `CIRCLE` / `CIRCLEBF` を追加

## 0.1.1
- 起動引数 `--exec-mode {main,thread}` で実行モデルを切替（既定 main）
- main モード: メインスレッドが毎フレーム VM を駆動し、VSYNC命令（フレーム区切り）が有効
- thread モード: VM を別スレッドで実行（0.1.0 と同じ）、VSYNC命令 は no-op
- main モードの1フレーム実行量を指定する `--steps-per-frame` を追加
- バージョン表記から "prototype" を削除

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
