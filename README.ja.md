# PyxelBasic

[English](README.md) | 日本語

[Pyxel](https://github.com/kitao/pyxel) 上で動作する、行番号方式の古典的 BASIC インタプリタです。
レトロな BASIC の雰囲気を再現しつつ、Pyxel の画面・グラフィック・入力を扱えます。

> 現在はプロトタイプ版（v0.0.5）です。

## 特徴

- フルスクリーンエディタ：カーソルを自由に動かして行をその場で編集（挿入／上書き、Home/End、Backspace/Delete）
- 行番号方式のプログラム編集（入力・上書き・削除、`LIST` / `RENUM`）
- `GOTO` / `GOSUB` / `IF...THEN` / `FOR...NEXT` などの制御構造
- 数値・文字列の変数と多次元配列
- 文字列・数学・乱数・入力の組み込み関数
- 点・線のグラフィック描画とテキスト画面
- `VSYNC` による柔軟なフレーム制御（命令単位で同期点を ON/OFF できる）
- プログラムのファイル保存・読み込み（`SAVE` / `LOAD`）

## 必要環境

- Python 3.10 以降
- [Pyxel](https://github.com/kitao/pyxel)

```
pip install pyxel
```

## インストール

```
git clone https://github.com/TakeshiMaeda/PyxelBasic.git
cd PyxelBasic
```

## 使い方

```
python main.py                      通常起動（編集モード）
python main.py hello                起動時に hello.bas を読み込む（短縮形）
python main.py --load hello         上と同じ
python main.py --load stick --run   読み込んで自動実行
python main.py --workdir ./mybas    SAVE/LOAD 用ディレクトリを指定
python main.py --showfps            フレームレートをタイトルバーに表示
python main.py --version            バージョンを表示して終了
python main.py --help               ヘルプを表示して終了
```

オプション:

- `--load FILE` 起動時に読み込むプログラム。
- `--workdir DIR` SAVE/LOAD が使うディレクトリ。起動時に固定され、インタプリタ内部からは
  変更できない。省略時は同梱の `samples/`。
- `--run` 読み込んだプログラムを自動実行する（`--load` が必要）。
- `--showfps` 実フレームレートをウィンドウのタイトルバーに表示する。
- `--version` ウィンドウを開かずにバージョンだけ表示して終了する。
- `-h`, `--help` ヘルプを表示して終了する。

起動するとフルスクリーンエディタになります。どこでも行を入力し、Enter でカーソル位置の論理行を投入します。

```
10 PRINT "HELLO, WORLD!"
20 FOR I = 1 TO 3
30 PRINT "COUNT="; I
40 NEXT I
RUN
```

- 行番号付きで入力するとプログラムに追加されます（同じ行番号で上書き、行番号だけ入力で削除）。
- カーソルキーで自由に移動してその場で編集できます。`Insert` で挿入／上書き切替、`Home` / `End` で行頭／行末へ移動、`Backspace` / `Delete` で文字削除。既存の行を直すときは `LIST` で表示し、カーソルをその行へ動かして書き換え、Enter で修正します。
- `RUN` で実行、`LIST` で一覧、`NEW` で全消去。実行中に `Ctrl+C` を押すと中断して編集モードへ戻ります。
- `SAVE "名前"` / `LOAD "名前"` で `samples/` 配下に保存・読み込みできます。

## サンプル

| ファイル | 内容 |
|---|---|
| `samples/hello.bas` | HELLO WORLD |
| `samples/count.bas` | FOR/NEXT と式の利用 |
| `samples/graph.bas` | 線・点によるグラフィック描画 |
| `samples/stick.bas` | 方向キーで点を動かす例（STICK 入力） |
| `samples/meteo.bas` | 方向キーで上から降ってくる隕石をよける（当たり判定なし） |
| `samples/alltest.bas` | 全命令・関数を一通り動かすセルフテスト（機能ごとに OK/NG を表示） |

読み込んで実行する例:

```
LOAD "graph"
RUN
```

## 言語仕様

実装済みの命令・関数・演算子の**完全なリファレンス**は [docs/REFERENCE.ja.md](docs/REFERENCE.ja.md) を参照してください。

主な要素:

- 命令: `PRINT` `INPUT` `LET` `GOTO` `GOSUB`/`RETURN` `IF...THEN` `FOR...NEXT` `DIM` `DATA`/`READ`/`RESTORE` `CLS` `LOCATE` `COLOR` `PSET` `LINE` `RANDOMIZE` `VSYNC` `END`/`STOP`
- 関数: `LEN` `LEFT$` `RIGHT$` `MID$` `CHR$` `ASC` `STR$` `VAL` / `ABS` `SGN` `INT` `FIX` `ROUND` `SIN` `COS` `TAN` `ATN` `RAD` `DEG` `EXP` `LOG` `LOG10` `SQR` / `RND` `INKEY$` `STICK` `BUTTON`
- 演算子: `+` `-` `*` `/` `MOD` `^` / `=` `<>` `<` `<=` `>` `>=` / `AND` `OR` `NOT` `XOR`

## プロジェクト構成

```
PyxelBasic/
├── main.py                起動スクリプト
├── pyxelbasic/
│   ├── interpreter.py     インタプリタコア（字句解析・式評価・実行エンジン／Pyxel非依存）
│   ├── console.py         Pyxelテキストコンソール兼グラフィック面
│   └── app.py             編集／実行／入力モードの統合とメインループ
├── samples/               サンプルプログラム（.bas）
├── tests/
│   └── test_core.py       コアのヘッドレステスト
└── docs/
    └── REFERENCE.md       完全な言語リファレンス
```

## 開発・テスト

インタプリタコアは Pyxel に依存しないため、ヘッドレスでテストできます。

```
python tests/test_core.py
```

字句解析・式評価・制御構造・配列・文字列関数・INPUT・グラフィック命令・フレーム制御・RENUM などを検証します。

## 未実装（今後の予定）

- グラフィック: `BOX` / `CIRCLE` / `FILLCIRCLE` / `SPRITE` / `SPRITEDEF` / `PCG` / `PALETTE`
- サウンド: `PLAY`（MML）
- 制御構造: `ELSE`、マルチステートメント（`:`）
- 文字列エスケープ（`\n` `\cN` など）、日本語フォント

詳細は [docs/REFERENCE.ja.md](docs/REFERENCE.ja.md) の「未実装・制限事項」を参照してください。

## ライセンス

[MIT License](LICENSE) で公開しています。

Copyright (c) 2025-2026 Takeshi Maeda (SPSoft)

## 謝辞

本プロジェクトは [Pyxel](https://github.com/kitao/pyxel)（MIT License, © Takashi Kitao）上で動作します。
素晴らしいレトロゲームエンジンを公開してくださっていることに感謝します。

PyxelBasic は Pyxel を利用した**非公式**プロジェクトであり、Pyxel 本体およびその開発者とは関係ありません。
"Pyxel" の名称は原作者に帰属します。
