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
- `samples/meteo.bas`：方向キーで上から降ってくる隕石をよけるサンプル（当たり判定なし）。

### Changed（変更）
- ドキュメント：フルスクリーンエディタに合わせて README を全面的に書き換え（廃止した `]`
  プロンプトの記述を削除し、その場編集と `Ctrl+C` 中断を明記）。機能一覧にエディタを追加し、
  同梱サンプルをすべて掲載。

### Known limitations（既知の制限）
- ダイレクトモードでは 1 行 `FOR`/`NEXT` ループは動かない（`RUN` 中のみ）。
- 1 行内でネストした `IF ... THEN IF ... THEN ... ELSE ...` の `ELSE` の結び付きは
  保証しない（best-effort）。

## [0.0.5] - 2026-06-14

### Added（追加）
- `--showfps` オプション：ウィンドウの実フレームレートをタイトルバーに表示（毎秒約 2 回更新）。
  指定しなければ計測オーバーヘッドはない。

### Changed（変更）
- 行入力時にコード部を大文字化（文字列リテラルと `REM` のコメント本文は入力したまま保持）。
- `RENUM` で `REM` 行を残すようにした。
- `samples/game.bas` を `samples/stick.bas` にリネーム。

## [0.0.4] - 2026-06-14

### Added（追加）
- `Ctrl+C` で実行中（または `INPUT` 待ち）のプログラムを中断。`BREAK in line N` を表示し、
  プログラムを保持したまま編集モードへ戻る。
- `Esc` で終了確認ダイアログを表示（`Y` で終了、`N`/`Esc` で取消）。Pyxel 標準の
  Esc 終了は無効化。
- `VSYNC CLEAR`：自動フレーム区切り対象をすべて解除（以後は明示的な `VSYNC` のみで区切る）。

### Changed（変更）
- テキスト描画を最適化：dirty フラグ付きの焼き込み画像から描画し、通常フレームは
  文字ごとの描画呼び出し数千回ではなく 2 回の `blt` で済む。画面が埋まっても
  フレームあたりのコストが一定。

### Fixed（修正）
- 小数（`0 < |b| < 1`）での `MOD` が除数を 0 に整数化して Python の `ZeroDivisionError`
  でクラッシュしていたのを修正し、BASIC の除算エラーを発行するようにした。

## [0.0.3] - 2026-06-14

### Added（追加）
- フルスクリーンエディタ：出力と編集でカーソルを共用（`PRINT` はカーソルから流れ、
  `LOCATE` は移動のみ）。矢印キー・`Home`/`End`・挿入／上書き切替（`Insert`）・
  `Backspace`／`Delete` でその場編集でき、論理行は折り返し・リフローする。`Enter` で
  カーソル位置の論理行を投入。`]` プロンプトを廃止。
- `main.py` の `argparse` による起動オプション：`--load`、`--workdir`（SAVE/LOAD 用
  ディレクトリを固定）、`--run`、`--version`、および位置引数の短縮形。バージョン文字列は
  `pyxelbasic/version.py` に置き、`App` を遅延 import するため `--version` は Pyxel も
  ディスプレイも不要。
- コード化エラー：全メッセージを `pyxelbasic/errors.py` に一元化（single source of truth）。
  100 番台で分類し、出力にコードを表示。
- `samples/alltest.bas`：全命令・関数を一通り動かすセルフテスト。テストスイートからも実行。

### Changed（変更）
- 命令として成立しない行は `Expected '='` ではなく構文エラーを報告するようにした。

## [0.0.1] - 2026-06-14

### Added（追加）
- Pyxel 上で動く行番号方式 BASIC インタプリタの初期プロトタイプ（開発中）。
- データ駆動の予約語ディスパッチ：予約語→ハンドラメソッドの対応を
  `pyxelbasic/keywords.py` に一元化（single source of truth）。

[Unreleased]: https://github.com/TakeshiMaeda/PyxelBasic/compare/v0.0.5...HEAD
[0.0.5]: https://github.com/TakeshiMaeda/PyxelBasic/releases/tag/v0.0.5
[0.0.4]: https://github.com/TakeshiMaeda/PyxelBasic/releases/tag/v0.0.4
[0.0.3]: https://github.com/TakeshiMaeda/PyxelBasic/releases/tag/v0.0.3
[0.0.1]: https://github.com/TakeshiMaeda/PyxelBasic/releases/tag/v0.0.1
