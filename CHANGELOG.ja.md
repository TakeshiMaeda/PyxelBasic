# 変更履歴

[English](CHANGELOG.md) | 日本語

PyxelBasic の主な変更点をこのファイルに記録します。

形式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に準拠し、
バージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従います。
本プロジェクトは `0.0.x` のプロトタイプ段階のため、リリース間で互換性のない変更が入ることがあります。

## [Unreleased]

### Added（追加）
- `IF ... THEN ... ELSE ...`：`IF` の偽側に対応。各側は行番号（暗黙の `GOTO`）でも、
  1 つ以上の命令でもよい。
- `:` 区切りによる 1 行複数文。`RUN` 中はプログラムカウンタが文単位で進むため、
  `FOR ... : ... : NEXT` の 1 行ループや、`GOSUB 100 : PRINT "BACK"` のように
  `GOSUB` から戻った後の同じ行の続きも正しく実行される。

### Known limitations（既知の制限）
- ダイレクトモードでは 1 行 `FOR`/`NEXT` ループは動かない（`RUN` 中のみ）。
- 1 行内でネストした `IF ... THEN IF ... THEN ... ELSE ...` の `ELSE` の結び付きは
  保証しない（best-effort）。

## [0.0.5] - 2026-06-14

最初の公開リリース。

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

[Unreleased]: https://github.com/TakeshiMaeda/PyxelBasic/compare/v0.0.5...HEAD
[0.0.5]: https://github.com/TakeshiMaeda/PyxelBasic/releases/tag/v0.0.5
