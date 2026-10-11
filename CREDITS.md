# 素材、工具与许可

## 片中素材

- NEXA 标识与 VI：来自用户提供的项目品牌素材，保持原标识；本片按其配色与 Noto Sans SC 字体要求制作。
- 实际应用录屏：`ryanshang2024/codex-cloud-nexa`，revision `40e0bf45f74a025641e9dc88953987a7a149732e`；独立 DEMO 租户，无真实企业或联系人。
- 中文文稿及背景音乐：为本片制作。音乐采用自行合成的正弦和弦/琶音，不含第三方录音。
- 中文旁白：离线 Kokoro 中文合成语音 `zf_xiaobei`，已明确区分模拟资料、真实接入与人审。

## 随源包分发的第三方组件

| 组件 | 版本 | 许可 / 说明 |
| --- | --- | --- |
| GSAP | 3.14.2 | GreenSock Standard no-charge license，https://gsap.com/standard-license/；保留 `film/assets/gsap.min.js` 中版权声明；不宣称 MIT/Apache |
| Noto Sans SC | @fontsource 5.3.0 | SIL Open Font License 1.1；完整许可随字体保存在 `film/assets/fonts/LICENSE` |

## 用于制作 / 重建的工具

这些工具及模型权重未随源包分发，依赖通过 `package-lock.json` 锁定或此处记录。

| 工具 | 版本 | 许可 / 上游 |
| --- | --- | --- |
| HyperFrames | 0.8.147 | Apache-2.0，https://github.com/heygen-com/hyperframes |
| Kokoro ONNX wrapper | 0.6.1 | MIT，https://github.com/thewh1teagle/kokoro-onnx |
| Kokoro 82M 模型 | v1.0 | Apache-2.0，https://huggingface.co/hexgrad/Kokoro-82M |
| Misaki 中文 G2P | 0.9.4 | Apache-2.0，https://github.com/hexgrad/misaki |
| jieba | 0.42.1 | MIT；包源代码与 setup.py 已审查，按上游文档手动复制 Python 模块，没有执行其安装脚本 |
| pypinyin | 0.55.0 | MIT |
| cn2an | 0.5.23 | MIT |
| SoundFile | 0.13.1 | BSD-3-Clause |
| ordered-set | 4.1.0 | MIT |
| Playwright | 1.64.0 | Apache-2.0；复用项目已有依赖 |
| Chromium / FFmpeg | 系统预装 | 使用当前环境系统二进制；源包不分发这些二进制 |

使用轮子安装 Python 工具，NPM 安装禁用生命周期脚本。HyperFrames 初始化时曾尝试额外下载技能安装器；该下载因缓存目录不可写失败，未执行下载脚本。本片采用当前会话已审查的 HyperFrames Skills，未再调用该安装器。

## 模型下载核对

从模型作者的 GitHub release 下载，SHA-256 与 release asset metadata 一致：

- `kokoro-v1.0.onnx`：`beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a`
- `voices-v1.0.bin`：`bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d`

完整影片重渲染使用源包现成 WAV，不需要重新下载模型，不需要销售 API 密钥，不需要外部 TTS 服务。
