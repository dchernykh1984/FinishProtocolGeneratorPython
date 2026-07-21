# Changelog

## [0.1.1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.1.0...v0.1.1) (2026-07-21)


### Bug Fixes

* reliable release builds (linux-aarch64 on ubuntu-24.04, drop Intel macOS) ([5f2f241](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5f2f24103565200a31a71c6e8b77faa5a7b070ad))

## 0.1.0 (2026-07-21)


### Features

* add configurable finish time and gap labels (UI, config, save/load, HTML) ([2449976](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/24499762c53ff0362793c4874810f736194fc8e8))
* add configurable labels for Weather, Track, Organizer, and Overall results ([ad09be0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/ad09be002712c5b34098266d6d46c32a0c15ed83))
* add configurable n_finished_laps_label ([1ee1123](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1ee11233ad27ee8618ebe22c41f2004cad430050))
* add leader gaps and per-lap gap deltas to live stats ([5eedbd7](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5eedbd7fa103ee4e9ca8ec2fb1b134bb428c96b8))
* add missing UI controls and fix C++ config parity (label fields, logger, laps diff, SCL, lifecycle, flag reset on load) ([f38d41c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f38d41c479735ba5d73cea3ed63d0dd9552c3eb6))
* add per-lap deltas of the leader gap to live stats ([4994372](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/499437219eecf9cde3f84ff041369fb6a04a3df4))
* add site start-list source merging all device lists ([5032abb](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5032abb94291b92eb4f956d7134207e160b22d74))
* add site-matching UBT protocol template ([769c0d4](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/769c0d4eafca41a6707613a56dedea5032585f79))
* add site-matching UBT protocol template ([#50](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/issues/50)) ([28cf3f8](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/28cf3f886bfee0e1dc19596e1127673b18346fce))
* add template_file to config, UI and load/save ([584dd4b](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/584dd4bfc81f0be6cc15fb652bf8dd6f4ba74401))
* add trailing newline in HTML output ([34a801c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/34a801cd3bfea048559721d0ba90302717d29ebd))
* enable auto-refresh in example config (RefreshProtocol, interval 10000) ([3c0fd89](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/3c0fd890478730d82cf10e640b1afa1d76faf8d1))
* format live-stats gaps with the configured decimal seconds ([4f214da](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/4f214dae487e914e6390e64e7d221caceb92b0ae))
* HTTP upload tab — send protocol to cycling-site endpoint ([2b5052b](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2b5052b19036b49e725b2329fc58a6885833a514))
* **http:** delete the unchecked protocol from the site when publishing the other ([f65cd3c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f65cd3c3be48fc2ab3835578d99d1f1fb1e50a0b))
* **http:** fetch group/finish/remote timings from site; rename HTTP tab and source labels ([4458915](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/44589154418e3b6c76a17d78f8f5934ebd44284b))
* **http:** replace upload checkboxes with per-protocol Nothing/Upload/Delete action ([9da5e23](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/9da5e23be6ff0b4d72064682d334c6d7f963de9e))
* implement FTP download tab with merge-by-id and background download worker ([3a368cf](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/3a368cf22386a31059bfb5470c4307d69e97ceb5))
* implement UploadGroups/UploadAbsolute FTP upload after generate ([4851f98](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/4851f980d864a26daf6c517dc96c04b36b0fd011))
* make lap rank column labels configurable (lap_rank_label, lap_finish_rank_label) ([3fae0d9](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/3fae0d99bd53e35d3ce1a9dade0cf3f5175f94b3))
* migrate protocol upload to /api/v1/protocols/upload/ with competition_token ([#15](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/issues/15)) ([184d6fd](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/184d6fddcb2c1943b6835e7376c002aedc06e757))
* move lap name/additional info labels to Columns tab ([998acdc](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/998acdc0d4d75e463315260aabe5c6fcc6ad7845))
* port FinishProtocolGenerator from C++ to PySide6 ([9aece9f](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/9aece9f3dbb18c76b2dac97454007ae7e3c9a427))
* port Show/Hide collapsible buttons from C++ with configurable labels ([3b4c686](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/3b4c686bb2e38d26411b124d0b04fa0c01988a03))
* resolve app data next to the executable for portable builds ([fa6edd9](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/fa6edd9cd93a2da85fc97ec7e5e8adf639e2dc03))
* send live per-competitor stats to the site for the Garmin data field ([5b96814](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5b9681427a961ecdbd5cf08a578d696d3144b5c6))
* set app name and icon at QApplication level for dock/taskbar ([a394691](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/a3946913ca739138c9816cf8f9fb60ef7e5b01c6))
* show DSQ reasons with their location in the finish-time column ([17853ad](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/17853adbb6d8bce1fd8e396946ec46d1e2dff1c3))


### Bug Fixes

* add spacing between CP-splits and all-buttons in group and absolute protocols ([1394fc7](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1394fc7558d1744f628288e2535e9bd4e26668f5))
* block auto-refresh on load, fix mypy w-variable reuse, regenerate golden HTML ([ac92ac0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/ac92ac0e4269c33c881ee7084d107305fce09152))
* check protocol before uploads, fix manual FTP "Download complete." after errors ([af45cf2](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/af45cf261b2e0ec65b425186524922bbccad25e7))
* convert RefreshProtocol between seconds (Python) and milliseconds (C++ format) ([43307b8](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/43307b8481669a15a4a8b5cac1d3220908e6ab09))
* derive skip_first_lap from race type (Custom Start, Number of Tries) ([23cb2ab](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/23cb2abadf8ec9411d97e3777165b5cb7c3468f5))
* DNF (group started, 0 laps) now sorts before DNS in absolute and group protocols ([445d729](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/445d729ecea5bd00beeb56b951ec0caf1c7dd71c))
* FTP download errors no longer cancel generation, reject ftps ([a32df24](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/a32df249e56245f7163983142dd52a4a819e4ce3))
* hide split cells when athlete has no CP data in current lap ([5a9d511](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5a9d5114a482cef48374988cffa71158513f90ee))
* **http:** keep site timing sources from being overwritten by FTP ([ebbd80c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/ebbd80c68185d6ffde0abdc8327a2020b9c8e28a))
* **http:** persist data-source selections across race-info save/load ([ad66920](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/ad66920516f6c50f44dc8661a9fd19793e0c740b))
* **http:** treat unknown HTTP action value as Nothing instead of Delete ([a54570d](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/a54570d7a6e58baeb902039763c2dd9a39d4e563))
* **live-stats:** report the gap to the rider behind as negative ([93278d8](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/93278d83912762c064916ee210db5cf83029f2bf))
* log FTP upload errors with details at end of generate log ([dc1e700](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/dc1e70079501ccc33b26bb7fb1aa5f3894159f12))
* map C++ race type display strings to Python constants on config load ([0a77156](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/0a77156171ce5a27e10b99dd3d4e3aa28bd3aa77))
* port NumberOfTries validation, text protocol format, crossing diagnostics, Eliminator Finals guard ([6cc79e1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/6cc79e1226d440d8e26eac9dd7002eda5e3e340d))
* rank live-stats places by lap finishes only, ignoring control points ([d95f6a7](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/d95f6a7dfc36c81f683297eee24ef9c78b9a6f0e))
* remove extra lap added to n_laps in custom start (skip_first_lap) mode ([1a5b0d3](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1a5b0d3a61900d2110187a65911ceca888ee1de0))
* remove hardcoded "Lap {name}:" prefix from lap finish rank header ([862b9ad](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/862b9ad53663c535dc0859a68ac45aa0585f80de))
* remove hardcoded "Lap {name}:" prefix from lap finish rank header in absolute protocol ([8cdc8ad](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/8cdc8adb7425217860c0054c517bca01b34d0734))
* remove hardcoded "Race " prefix from race name in protocol header ([273152d](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/273152d5e727c3d8282fd2b3b48d889402b1cc44))
* remove old comment block from template_romashkovo.html ([fe774fb](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/fe774fb35b7a924e9dc2d50509f9c8a61e0f4ed6))
* remove redundant success popups ([3f0bcbf](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/3f0bcbfb39a29e85441303047cd125771f5bec04))
* resolve dev data path against the working directory ([f6c0d6c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f6c0d6c85e1e676bcc424e219c9afaca58d02314))
* show DNF for started groups and lap columns based on configured laps ([27ce4a5](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/27ce4a56b9b9149951cf9ee95a9e93430db16266))
* show lap splits in 1-lap races when intermediate control points are present ([0109ea0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/0109ea09d1b231db2412d5a3dd31c9476e9fb4d5))
* show UNKNOWN for uncrossed CPs and in-progress lap time; show splits in 1-lap race and group protocol with hide_empty_columns ([da90b03](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/da90b031788bc15423a65cabc70f4f24d9cc8f25))
* show UNKNOWN lap time only when athlete has CP data in current lap ([aae1182](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/aae1182c43d2c9c8c85e836dc89dd406cc118d0f))
* **sort:** use ascending competitor number as lowest-priority tie-breaker everywhere ([eb03d9a](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/eb03d9a3c4318fbd77813280744ccb4f0fd1b165))
* start auto-refresh timer on config load, not only on checkbox toggle ([90df0c8](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/90df0c8b387fb42598339163b2f66be04d0f2614))
* supplement group_list from start protocol (groups with no start time show as DNS) ([da77d47](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/da77d474dc677ef51e3b94f10bb57333ebadb4fb))
* sync all UI widgets after loading race info, remove reopen popup ([ceaa06c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/ceaa06c7e522baa4fbe390bbf60f870d99f50c33))
* **tests:** add LapRankLabel/LapFinishRankLabel to test fpg_info.txt ([7ba4d8a](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7ba4d8a99b5462e8fa1e2dc25cb78259b7f9a40b))
* update default config ([8172c23](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/8172c2345181660a16ef86d18d35a036b11758f7))
* update golden HTML — last DNS→DNF entry for started group (bib 567) ([f3a97ea](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f3a97ea9ec8f78f32408a0d5bce4c41d1284fc48))
* use Path for remote-points path construction, no trailing-slash hack ([4081664](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/4081664fdffefbbc56bb13390ebb1484862b568c))
* UseStartCheckList stores FTP action, not file path, in C++ positional format ([ea5d3f8](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/ea5d3f870011cb39555f8e4939e45fb5ce77f7c3))


### Documentation

* add contributing guidelines to README ([7c0a5c7](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7c0a5c7d367aef7db13a6028a6abf6b5850f4bc5))
* add Running the application section to README ([a653425](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/a653425fb2a30cf202f90b547bc9c2162db7b393))
* add setup instructions to README ([b05b90b](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b05b90bde806b31ac44818316e4cfc098f6f9849))
* document pre-commit setup and manual run command ([c08758c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/c08758cf97d82549b22a8ec3df6dd9002143c4c3))
* document the live-stats fields in the README ([98065e4](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/98065e49064207f9e0b245d44a4a10b1dccd621b))
