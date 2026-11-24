# Changelog

## [0.18.2](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.18.1...v0.18.2) (2026-11-24)


### Bug Fixes

* **calculator:** a control point penalty before the last lap stays in the result ([f9c9be9](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f9c9be9557cc994949fa62790d238eb5f34caef4))
* **calculator:** the laps difference check names an attempt by its own number, not by its count ([c367c65](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/c367c65ce6894a2314f69a9338024ed58d130f8b))
* **config:** Merge by competitor number (ID) only is saved with the race info ([17a24db](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/17a24db43553d914fcde72c402328fe71dcd52c7))
* **files:** a UTF-8 byte order mark is read past, not into the first line of an input file ([e6b067c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/e6b067cfb34374bcf0bd6c7e0a776057e2e37024))
* **protocol:** a legacy Number of Tries rider with no attempt under Disable DNF has no result, not a crash ([7950fdb](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7950fdbff1d7c9f81407c432fb179c5cad9e087a))
* **protocol:** laps equal to the recorded millisecond share their lap rank ([beb474a](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/beb474aeeaf8d38e2656733850e5b50028be2beb))


### Documentation

* a rider who has not started reads DNS in the live statistics, not a number ([87fbb5e](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/87fbb5e18d898e7c5ec52e08e4f4c64d165f78d4))
* the protocol section is written after the settings an older version knows, no longer the last line ([70d7ebe](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/70d7ebe5f724deece04304e40c1e75740aa950e4))

## [0.18.1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.18.0...v0.18.1) (2026-11-24)


### Bug Fixes

* **calculator:** legacy Number of Tries riders without an attempt sort by number, not into a crash ([645b7ce](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/645b7ce7db19260eb5dd5319844a140703dd016e))
* **calculator:** Number of Tries orders rule sums to the recorded millisecond, as its places read them ([1576f82](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1576f822b77e011dcd9a40cd8a17aa9432a66e53))
* **protocol:** a Number of Tries tie-break parts the place it breaks ([269a153](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/269a153a0db5c9292628867c9b3643ca87da9b4f))


### Documentation

* a Number of Tries tie-break parts a place, a tie on every rule shares one ([58e55f2](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/58e55f276444306289a8b0a611147592985bf35f))
* **calculator:** a same-millisecond pair is left out of the warning, shared or parted by a later rule ([4de9948](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/4de9948ab66cb2c458d3701feaccd5c881462ace))
* **constitution:** in Number of Tries a place is shared only on every scoring rule ([c2f7433](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/c2f74334e0776616ada4ff4ce623c1ab0c43c568))
* **protocol:** group places are shared as shared_places shares them, not by the printed time ([99fd0d3](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/99fd0d3fe1adda4c3cf3b9f7018073f8cf3dddc7))
* **specs:** mend the line break the rules bullet's rewrap left behind ([c77d1e0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/c77d1e054446f65b7429cca26f45325e950f3c17))
* **specs:** Number of Tries compares its sums to the recorded millisecond ([1627ba1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1627ba1d81ffefc62bbb7271618c0f81f7265b21))

## [0.18.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.17.1...v0.18.0) (2026-11-24)


### Features

* **calculator:** a rider who missed the start check is DNS, after the DNF riders ([eef4a07](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/eef4a072f59264a90372d4dc8306f095516559d8))
* **calculator:** report a group the group times file lists more than once ([5eac369](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5eac369e5e40889ecb10634252fedfcd2ce032d9))
* **live:** a rider who has not started reads DNS on the watch, out of the numbering ([bbda667](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/bbda667856e4cd7c8dbc838cddb6e180a3a2e528))
* **ui:** Disable DNS, everyone counts as started, saved with the race ([e696445](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/e696445799110fcd542a463b766f1d1d1c2f44e7))


### Bug Fixes

* **calculator:** a group start of 0 is no start, as for the finals and the start board ([39ce1af](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/39ce1af40102d577ae3298b31bf5bdd6809f7be3))
* **calculator:** a group without a start time is a warning until one of its riders has a mark ([27c3856](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/27c3856c94af8e2138e274275669cbc747d4a403))
* **calculator:** a group without a start time is an error and its riders did not start ([7b03c42](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7b03c42014a9df33a4d9e8d7bd1a4c0ee49f0c24))
* **calculator:** a rider who never started still shows his Spiridonov coefficient ([e920923](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/e9209230eca9c6bfb252593da56567b3db6e3bed))
* **calculator:** a rider whose start was never seen is not checked against the start check list ([cf09dee](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/cf09deeca84c8b57508c85190fa4dbda0bbd686e))
* **calculator:** the no start time error says what is lost, true with Disable DNS too ([69b5646](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/69b56467c3ad3b356e7484aa1864383258b38a8b))
* **config:** a generated file is refused the control point streams and fpg_info.txt ([fcb97eb](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/fcb97eba1d0a156cd3627926c99b9307f158c81e))
* **http:** a bad control point number is named in the error, not called missing ([f7e5618](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f7e5618f9e5e2b2c5dc5f3d0165965b37dba8aab))
* **http:** a control point number from the site must be a whole number ([5f63520](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5f63520abdd50a7d4571647f86431c6674fbb5bc))
* **http:** a control point number must be plain digits, not any digit isdigit takes ([234da24](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/234da24bf23453e05e1345d867e7f1189344345e))
* **http:** a control point the site lists twice is refused, not overwritten ([62470f8](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/62470f8b32ad695496ff20636085ed0b76341b5d))
* **http:** a device or point the site sends without items keeps the local file ([9819f68](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/9819f689e10fe4edd8783942b78ccf24a38f1f58))
* **http:** a fetch error never repeats the competition token in the log ([214cc3f](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/214cc3f95dff290e212472c26ca5b1bf491682c9))
* **http:** a negative control point number is named for what is wrong with it ([80a785f](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/80a785fe9e38643cb23bed6fa22da65baea5064a))
* **http:** a site answer without its devices or points keeps the local file ([2e02628](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2e0262863b3f3b6b35acc66e2380889a600df7b7))
* **http:** a site that fails after taking a fetch is logged, and the run goes on ([ca245a4](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/ca245a462a6316982e737612210cfc0cca9baf70))
* **http:** a site URL without http:// is a bad URL, not a bad answer ([dd24c22](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/dd24c22c4279d42f3f99ff35964084068766d1df))
* **http:** only the URL's token is blanked out of a fetch error ([4fe1431](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/4fe1431bc1bd04a9a24abeefea96fb8a3b894648))
* **live:** a DNS of the start check stays out of the live numbering, gaps and packs ([dec6070](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/dec607064f2e9d49de794215c6cddd9a1c6eda23))
* **live:** every DNS stays out of the live numbering, as the protocol says DNS ([5f6cd4c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5f6cd4ca3472a1b7257d45409cfeb2d15417f2bc))
* **protocol:** a DNS of the start check is never the leader the gaps are measured from ([ab585ef](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/ab585efef1cedcd60ff13db55f3ecbf60c0ccab6))
* **protocol:** a DNS of the start check needs Print DNF only when he did not finish ([3adfcfa](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/3adfcfa56c625c0138a3856914699ab5b16d12fe))
* **protocol:** a DNS of the start check shows his time without a gap ([b8ce500](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b8ce500b9d7936c240a4963d1be420169b618fc5))
* **ui:** a control point the site has beyond the configured count is a warning ([7644941](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7644941aeb669e2e9ddf7d99d59c4d8b2780219d))
* **ui:** a download step that stops says the downloads after it were not tried ([0c7c3dc](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/0c7c3dc951bae02ff6cc9690f2926484f24db3f2))
* **ui:** a download step that stops without words still names what stopped it ([7ca1e5e](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7ca1e5eb3eb1e4b5afc335dbbbc2a6a02a806679))
* **ui:** a site point outside the configured numbers is named outside, not beyond ([e0a13e2](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/e0a13e257839c7728347a5cd399ca1793958b9c9))
* **ui:** the key=value race info format reads Disable DNS as it reads DNF and DSQ ([fe22c61](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/fe22c61ed32734b127208bbbb7ac48b171c29dce))


### Reverts

* **live:** keep a rider who has not started numbered on the watch, as before ([8e7f094](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/8e7f09458400ea1c3fc42d138702e5c1d748ed4d))


### Documentation

* a plan or task list written from Spec Kit's templates is made ASCII before commit ([c02b822](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/c02b82221445bccd8c8dfee641be5cd89b0c4b12))
* adopt a constitution for spec-first changes ([0ae23cf](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/0ae23cfcbf3ff228a9d4dd76b75fbfba6ca8acde))
* **calculator:** say which settings change a rider who never started ([76b4a9e](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/76b4a9e2c20376d71c0564c1f6940408a8aa0f45))
* **calculator:** the order puts the statuses first, then the C++ comparison ([7c1f944](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7c1f944077553f4654bdce762206a2284f6109f5))
* **constitution:** a generated file is refused every file of the race ([088f044](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/088f0441d3ca98244d30f4566cc1855f2288d9c5))
* **constitution:** live statistics rank from lap finishes alone, outside the shared calculation ([9803469](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/98034698897b5c5ed19a2ec643c811da4e36ade2))
* **constitution:** name the files the ASCII rule leaves out ([b1c24ae](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b1c24aebe11ea1725675f9c3a872f6b44f337b89))
* **constitution:** name the input files a generated file is refused ([18dedc2](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/18dedc2d03515da8459c00819fb3e0f2bcf4fc93))
* **constitution:** record where the code does not meet a principle yet ([1fabdc4](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1fabdc4023ff44e6c3a42c9136cea1be3d2e68bc))
* **constitution:** state the gaps in the principles, where they show ([4ee98cd](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/4ee98cd03e8ce756f5ed9dbf952bb790504b6839))
* **constitution:** the seeding protocol and live statistics do not share a dead heat ([1ed2ff0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1ed2ff0d466bc5e4913e779e214a1925cbad09a4))
* describe the generator as it works today ([d3a6475](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/d3a6475e171e1c2995996a78014682a328fc454b))
* opening issues waits for an explicit yes too, as speckit-taskstoissues does it ([0edad03](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/0edad039202037de725f34039735ddcd18b47a8b))
* **specs:** a decimal point in a time needs a digit after it ([bc144d7](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/bc144d70c2efcfa092f131d373c976d6e71b06c8))
* **specs:** a DNS of the start check rides in the live packs like any rider not DSQ ([5d0bbeb](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5d0bbeb7dd63f5bb1a440398e7380a80a0b75269))
* **specs:** a group the group times do not list starts at 0, its riders at their delay ([9afdc4c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/9afdc4c4e8923826285c70a7352c456aa2f630f3))
* **specs:** a live gap in Number of Tries is the difference of the results ([2a8c574](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2a8c5743c55d9ee3cf0a3bdccdcd6e69d41a106b))
* **specs:** a negative lap or stage count is kept as written ([28f6389](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/28f638933684ed55b25ece29536d49a7e47d817e))
* **specs:** a rider whose start was never seen is no finisher, settled after the order ([5182262](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5182262e9fecd23e4da41c4383024b4fc0cc7fd7))
* **specs:** a site answer of the wrong shape stops the run unreported ([f0d029c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f0d029cbd728fb8d26e0d11a194cc097e5d35ab3))
* **specs:** a site that times out after taking the request stops the run unreported ([3323f0c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/3323f0c0ee33a3fe1771239aed6bd7a686bce0df))
* **specs:** a time may leave out its seconds, and one that cannot be read ends the run ([f5d9e85](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f5d9e85e178f6a5f53b58bae3b1c31bccf660fee))
* **specs:** after an uncaught fetch only auto-refresh or a restart frees the buttons ([9f46092](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/9f4609283e747c3e85305b33384bbf091d9475d6))
* **specs:** break the start check DNS into tasks ([8d0d57b](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/8d0d57befc968c5f160e7c30ff41c4e952567489))
* **specs:** Disable DNS leaves the finals alone, where DNS means a heat still to come ([51915fa](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/51915fa2750251620a6c983153863e10bcdb8112))
* **specs:** each running worker gets its own 5 seconds at exit ([d5b0452](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/d5b0452b6db0ee9cfe25a05182080ef45ea4a472))
* **specs:** lap columns need Show lap times ([e4efb35](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/e4efb355fc850fb37a536d397559135fda9ec5e3))
* **specs:** legacy Number of Tries ranks by counted attempts, then their sum ([69b0688](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/69b068822a12eee9ab317e2fa1f2b20cb22e76f1))
* **specs:** list the seeding protocol's rules one by one ([43dd1a6](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/43dd1a6b9e5428a80fb0ea2fe167743be2b10b1d))
* **specs:** live statistics need a site URL ([d393056](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/d39305678b2e7c2c5492510e420d9e7a99f22470))
* **specs:** mend two line breaks a rewrap left behind ([1bff240](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1bff2404ffb3974a7d3192c85b71966fac35de37))
* **specs:** plan the start check DNS and Disable DNS ([80bbd07](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/80bbd074102ff61c5bc8a580a77966317d4a97e8))
* **specs:** rewrap the paragraphs that ran past the line width ([50f875c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/50f875c14580a21dea0dec7fe2c8b1f1ae33e5a5))
* **specs:** SC-004 names what else this pull request changes in the protocols ([b63a4f3](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b63a4f345edc8c4ab061dcdf731f3401ad67b0b9))
* **specs:** specify a rider who missed the start check as DNS, and Disable DNS ([a348cb7](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/a348cb78b59cd259234ffbcc38a4f385345cb17b))
* **specs:** the absolute protocol hides empty lap columns too ([f986b6e](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f986b6e0bf98aa5eddeddf0d967e83ad3a905408))
* **specs:** the double mark check compares finish and nextLap marks only ([a3f8ae4](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/a3f8ae46517962ce9b2bf7c7ce37f18b8cd75740))
* **specs:** the errors and warnings filter ignores case ([3a0d266](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/3a0d26626e558358668bd72a17074a0f98f0a256))
* **specs:** the lap columns come from the first rider with at least one lap ([4cf0d69](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/4cf0d692d677e851eb783fbde84d28949af8280b))
* **specs:** the lap rows and their buttons need Show lap times ([49c5c89](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/49c5c8906180af2369b89bef965cb37373f9445c))
* **specs:** the laps of a DNS still count in the lap statistics, as every rider's do ([2fbdc53](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2fbdc5315c09d3cb6d46e0685f72e7362c3d91d6))
* **specs:** the live place can read DNS as well as a number or DSQ ([68912e1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/68912e1a94d5e1db8ccbb37552a39d486b00255d))
* **specs:** the log file is created with its first line ([94b2d29](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/94b2d291789dd69f3ed8aa708fbb072402ffeef8))
* **specs:** the order compares the time from each rider's own start ([a161067](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/a161067f5322fb15b1dbc6e6aed14eac42353d8d))
* **specs:** the race info file and the template keep their blank lines ([24845f7](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/24845f77af378bd16b444346c0b2d0797f6da279))
* **specs:** the seeding protocol also takes the groups the group times do not list ([19fa4b6](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/19fa4b6b92fff7fcb3e45ecb9eba944c119a2cff))
* **specs:** the seeding protocol is written per line of the group times file ([b775a6a](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b775a6aa10033d73ebd35a5a1a41a2751160735e))
* **specs:** the seeding protocol writes laps and stages as read, an empty one as 1 ([f0ed3a1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f0ed3a1e1696b58e0a733f0d3a46229f7ef03684))
* **specs:** the time difference label is saved only with the finish time ([b1b7f99](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b1b7f990b99c9c39ab770a0325cf017a592697ff))
* **specs:** the uncaught site fetches are the exception to a logged failure ([25e6f04](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/25e6f04c50ed1a152187cbf87ec09893093187b0))
* **specs:** who finishes in Number of Tries without rules ([78274fc](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/78274fcaab2b56f3d5a444f6a0793854b6accddd))
* **specs:** with Disable DNS the start column still says NOT STARTED where no mark is ([880cb39](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/880cb394e7594a37785f958e435484e2b88ff01a))
* **specs:** with Disable DSQ a DSQ mark clears a start check list disqualification ([47466d8](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/47466d831a7150e960d480bfeb2e51e4991ab5e7))
* **specs:** with hidden empty columns a lap in progress past a control point shows ([2a79aa5](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2a79aa5f5e24550802b8cd14ee0309bac4809fd0))

## [0.17.1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.17.0...v0.17.1) (2026-11-09)


### Documentation

* **skills:** add the federation results protocol skill ([670fbbf](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/670fbbf09be8be1fd55b9d9472a436928af461eb))
* **skills:** the federation protocol covers a final not held, shared heat places and collect's refusals ([15a7e09](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/15a7e0904525c6288072893ae556d3493d37495e))
* **skills:** the federation protocol rules cover a missing small final and DSQ ([b8c5465](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b8c54651312238f1e2d690665c808a8d7eaae154))

## [0.17.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.16.1...v0.17.0) (2026-11-08)


### Features

* **finals:** a heat with no start of its own reads DNS for its riders ([accead7](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/accead7dfe8a0e6419e148b4ca3c653573361342))
* **finals:** a rider with no time in a heat that has gone off reads DNF ([28e461f](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/28e461f193e697e3728cf659a591e7a87c95fc1b))
* **finals:** print why a rider was disqualified, as the timed protocols do ([a5c885f](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/a5c885fbd55512466a0517296673f3c94b65d7aa))


### Bug Fixes

* **finals:** a heat that cannot be scored yet does not call its riders DNF ([1f5b6b6](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1f5b6b69677d0f7138b023f87fad33e6789d16fc))


### Documentation

* **finals:** the heat comments say what the status cells now do ([00295d0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/00295d07ea74f63e8d976ff975244d365e5f34cf))

## [0.16.1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.16.0...v0.16.1) (2026-11-08)


### Bug Fixes

* **ci:** let the release verify job read the release it checks ([35efbd7](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/35efbd7fb0407c2ba950c0000da2620d09b028e9))

## [0.16.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.15.0...v0.16.0) (2026-11-08)


### Features

* **finals:** show each rider's qualification place in the heat tables ([b89f93c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b89f93cd42da3c452c526e726306ea6e60b04105))
* **protocol:** give two riders with the same recorded result the same place ([8c84fab](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/8c84fabf6deafa3ad72270a9c82e455deaf8e9d7))
* **protocol:** share a place in Number of Tries when attempts and time both match ([93d7c4d](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/93d7c4d61624237c991fd148188f21fe2edfd59d))


### Bug Fixes

* **eliminator:** a repeat start closes other heats windows but not its own ([b70a9db](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b70a9dbe646df8fa4172b9e372374da4e0fdf2d5))
* **eliminator:** a rider who rode on after a disqualification is a warning, not an error ([2a9732d](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2a9732df78518b34beaf9a0b34a1874869b94118))
* **eliminator:** a shared start stays with the heat the chronometer offers first ([6917ed5](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/6917ed51e1e976bf5b15c290cd8f7a20ba21efd8))
* **eliminator:** a shared start time only refuses the heats that copied it ([c9c2fc4](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/c9c2fc4e3c0f70a38aa1bcf3da43412cc65b8516))
* **eliminator:** an empty repeat start line is not a second start ([079e58b](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/079e58b420b5a7088ed1a950e05a4cb59e71dbba))
* **eliminator:** give a late disqualification to the heat the rider last finished ([038e2ee](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/038e2ee2e207137cf5f5912d1bf6084f787cbedf))
* **eliminator:** ignore a heat's second start line entirely, boundary included ([c2eac09](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/c2eac0921f965f78ade91929f515d9c307746402))
* **eliminator:** keep the first start recorded for a heat and report the repeat ([d6e4d19](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/d6e4d19a2c2b78dae9dc8f50360b23a355dbea39))
* **eliminator:** leave a heat unscored when its recorded start cannot be used ([9ca8e5d](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/9ca8e5da2bacd1113d7b9e1706b2a6182e945755))
* **eliminator:** say which crossing the minimal lap time dropped ([29cd91b](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/29cd91be3f759627fb6b2024864dcd53e801d0c7))
* **finals:** a late disqualification lands in the rider's last started heat ([163c16f](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/163c16ff5b81664c4b6b1e0304d6dc2bdf6b7a11))
* **finals:** crossings from a heat with no start are not a laps setting ([f7ba456](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f7ba456714ace06450cfe4a59f24782901b6e39a))
* **finals:** the heat recorded first keeps a start time two heats share ([25eea38](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/25eea387c3d356221441f81885145ee719c82b94))
* **finals:** the shared-start error asks for the repair that works ([97c6d31](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/97c6d3150462f8e1c3a98b0529a129280cf9766a))
* **protocol:** a dead heat needs the same laps as well as the same time ([ec13946](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/ec139469c1334b8d79580513e4ac9899ebb49a79))
* **protocol:** call two times tied when the protocol prints them the same ([ec3a6c8](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/ec3a6c886990ad6d03cf91c48ad76a79569fb41f))
* **protocol:** clamp the printed precision so a bad setting cannot scale a time down ([39cdbef](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/39cdbeffebaae1b6fdc5219c66e9f5fbbe78ef87))
* **protocol:** do not call a shared total time unreadable in Number of Tries ([a7bc04a](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/a7bc04a78b10de33ad1230f99c738996937738aa))
* **protocol:** report a shared printed time only when the riders did not tie ([eb8253e](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/eb8253ecacfad97fb1511f2f40716412c1acce9e))
* **timing:** a recorded result prints the same from any time of day ([31c185f](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/31c185f374a7ae7645746c8d03772599a4a971fa))
* **timing:** compare only crossings when looking for one recorded twice ([4d38918](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/4d389180bec3bbc40ef934d92ee1f0f21ba20ee5))
* **timing:** Number of Tries marks are never one crossing recorded twice ([b71981c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b71981c9842a6c8d0cd46437614c45e929fc621b))
* **timing:** report one crossing recorded twice and drop it by the minimal lap time ([fbe1e52](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/fbe1e52babd96882b02f333f5bb62599feaea5d5))
* **timing:** results equal to the millisecond are ordered by number ([7de907a](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7de907ad466143042064b7f0ea6f6b36e913186b))
* **timing:** take the minimal time for lap as what makes two crossings one ([38cd0a9](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/38cd0a9628aba7c28a31fdecf35d014f1148d780))


### Documentation

* **readme:** the double-mark report is the minimal time for lap too ([6fe397f](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/6fe397fc8cd7c3be3168d3e975862aeda3f319ea))

## [0.15.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.14.1...v0.15.0) (2026-11-07)


### Features

* **eliminator:** a heat's time gives way before the number, place and name always stay ([3ed8a04](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/3ed8a048de6e7d16756580783f6de53a78af0822))
* **eliminator:** send the finals to the site as a ladder, its stages in the order ridden ([2860d6a](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2860d6a76ec1312c622f27c1ceca8fcc26a6c47a))

## [0.14.1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.14.0...v0.14.1) (2026-11-07)


### Bug Fixes

* **eliminator:** a heat with no usable start is logged, not put in a dialog ([7aaa925](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7aaa925312db02421973c05f6e737fee7ef1f2b1))
* **eliminator:** finals tables use the timed protocol's columns, so the number stays in view ([d039d27](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/d039d27f7a23296450f41e18cacf9e6e522621d8))
* **eliminator:** send each finals cell under its column, so the site draws the heats ([2be3092](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2be3092adbf409559c4923502707377c98e5456d))

## [0.14.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.13.0...v0.14.0) (2026-11-07)


### Features

* **eliminator:** place and advance a rider the moment he crosses the line ([77c011d](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/77c011d8724096ed0b73e2a912a00791c39e6cbf))


### Bug Fixes

* **eliminator:** a lap is not a finish, so say how many laps a heat is ([a9ed664](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/a9ed664be79c3de50c8fa8661db3d0df2f657803))
* **eliminator:** count every crossing as a lap, whatever the chronometer called it ([c686ddd](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/c686dddec4ec1893d44f7d35ab50119ad227cb34))

## [0.13.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.12.0...v0.13.0) (2026-11-07)


### Features

* **eliminator:** choose how qualification places are spread over the heats ([7974331](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7974331d607d39cc0225caddd57925255cf58927))


### Bug Fixes

* **eliminator:** a config without the seeding tag means the UCI scheme, not the last one ([f4edde9](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f4edde973361490831f04d14f8e6a9602626af9e))

## [0.12.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.11.0...v0.12.0) (2026-11-07)


### Features

* **eliminator:** let a meeting turn the small final off ([1b2a787](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1b2a78742ec05799238d3ba640ef7c98583ff0c4))
* **eliminator:** time the finals heats and move the ladders to their own file ([c6619d2](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/c6619d2c90bfdb4a52a005b3cca4471e7e7065cc))


### Bug Fixes

* **eliminator:** a heat is over only once a later one has started ([780fb0a](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/780fb0a9b06c55d78fbca393ea698c679420cfb4))
* **eliminator:** a heat saved with no start time is not a ridden heat ([6609aa8](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/6609aa8fa3101d8e7e0dfc9943ec2ce6cf9f570b))
* **eliminator:** a heat with no marks yet is in progress, not a heat everyone lost ([113a6de](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/113a6def24095ef37f195b677d026f3201178828))
* **eliminator:** guard the ladder file, order unraced heats by qualification place ([72c3359](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/72c3359c6f2f294cc17e034855375a6ae91c61fb))
* **eliminator:** refuse a heat start of midnight and keep the small final's places ([6f351e4](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/6f351e4d423f8ae8f72b0d212b76d7f1a4ed37fe))
* **eliminator:** refuse two heats on one start and keep a dead small final out ([adb8a10](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/adb8a102bef1e942ed339dd146e90c4770b6a400))

## [0.11.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.10.0...v0.11.0) (2026-11-07)


### Features

* **http:** publish protocols into a protocol section of the event on the site ([994b022](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/994b0229c422ca746698a3b4565f237df14e0053))


### Bug Fixes

* **ci:** restore the macos release asset, lost to a retired runner label ([d6a4b28](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/d6a4b28b241c56276d5dcac975cd447b1e07e9f4))
* **http:** a delete the site refuses says what the site answered ([83c5b61](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/83c5b61d216e187dc51e9c8f29ca0b858d41a19a))

## [0.10.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.9.0...v0.10.0) (2026-11-07)


### Features

* **config:** make the finals seeding export a setting with its own path ([5c37d2a](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5c37d2afebbf313fdbae742a2ef43f81646d5fec))


### Bug Fixes

* **config:** compare seeding paths the way the writers resolve them ([acb7649](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/acb764945f314154c6921f812cc16c7f8d1043c2))
* **config:** keep a bad seeding path from aborting the protocol run ([baa017d](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/baa017da60a262953f2e785575dcc368c39bad4c))
* **config:** never let the seeding protocol overwrite one of the race files ([db0218b](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/db0218bb6b5dc3584ed4d3eee5e62e2149f8f4f8))
* **config:** validate the seeding path as the writer sees it, name and all ([2a36937](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2a36937bab0fdcda1b53438e5fc69e25c8e029fb))

## [0.9.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.8.1...v0.9.0) (2026-11-06)


### Features

* **eliminator:** build the knockout ladder from qualification places ([4c1e476](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/4c1e47628ea4fbbfaafe8789d1183536d0ea6257))
* **eliminator:** generate the finals ladder as HTML and as data for the site ([bd431a9](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/bd431a99df3e66426c246e1d4185a10569f96808))


### Bug Fixes

* **eliminator:** number the small final after the big one even when ridden first ([2cbadbb](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2cbadbbd1da72c2110a5d42d66b235da1cf03825))
* **eliminator:** refuse a heat result that repeats a number or a doubled ladder ([c0e4fbe](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/c0e4fbe1841f487a4787694e5afba6be335674cb))
* **eliminator:** report two riders seeded onto one qualification place ([a1b908b](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/a1b908b935b859bece8472c4dea57cf7c18ff276))

## [0.8.1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.8.0...v0.8.1) (2026-10-24)


### Bug Fixes

* **document:** give each kind of column a rank of its own, so only the laps fall out together ([2252dd8](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2252dd8bcf1f912d259d2102fa7d6f458a14ae62))

## [0.8.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.7.0...v0.8.0) (2026-10-24)


### Features

* **document:** leave the date, place, course and sponsors to the site's event page ([cce8825](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/cce88256ae8745f057228a1b8a74139f5458f8e5))
* **document:** put a lap's statistics under its time behind their switch, as the HTML does ([6141cd6](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/6141cd66f20c4264d0cc13d04b9f02149d48a45b))
* **document:** rank the columns so a narrow screen leaves out extra info first and the start delay last ([fde3254](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/fde325421e2832e868ce98859f5223c5e27cf6be))


### Documentation

* **readme:** say what the protocol data leaves to the event page and how its columns are ranked ([64a3158](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/64a31586811a8973081e4fb4e6efcac062c855fe))

## [0.7.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.6.0...v0.7.0) (2026-10-24)


### Features

* **protocols:** build the protocol as a structured document for the site ([418ddae](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/418ddaeaffacd2f0332f3310fa7dcfba2843dbf6))
* **protocols:** send the protocol to the site as data, HTML or both ([e1f23fe](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/e1f23fe409c505662d70ba242c38968a07a03d91))


### Bug Fixes

* **protocols:** group a lap's columns only when it has more than one ([296b81c](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/296b81c4212206d48e46380924b550948a8a008d))
* **protocols:** keep a group whose name looks like a hashed id apart from the group it imitates ([e93a3f6](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/e93a3f62bd968d1edeafee974a878259bc652489))
* **protocols:** keep long group names apart with stable ids ([ad41c48](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/ad41c485d4e5c05e0b59ea6c86a984bf5ffd62a2))
* **protocols:** leave a rider without a group out of the group filter instead of breaking the document ([40edbfd](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/40edbfd2581dee63356c289b19e2829b0574625b))
* **protocols:** publish the HTML when the site refuses a data-only upload ([2335788](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/23357888d92035e376f9d902ea3c1edc30944497))
* **protocols:** send the protocol language only when it is a language code ([59a2719](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/59a2719ff6507ca3e43a62e573f50d5d15337ed7))
* **protocols:** show the loaded protocol format in the window ([8b89944](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/8b8994499536af7efc6cf4bf12b1423cb6cffbc5))


### Performance Improvements

* **protocols:** compute lap ranks for the document only when they are shown ([04d55de](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/04d55deea9c1006de9117a12669525e5eaccbd32))

## [0.6.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.5.0...v0.6.0) (2026-10-21)


### Features

* **tries:** configure scoring rules and attempt timing windows ([7ebd866](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7ebd866262e9efa9c881372e4c665ae8f033430d))


### Bug Fixes

* **tries:** align time gaps with scoring direction ([929f641](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/929f6419b3c9e24f3670dde67fa459adcaa14e15))
* **tries:** allow discarding unfinished rule edits on exit ([802af60](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/802af604f88f79036ac97f3a58985eecd9c87892))
* **tries:** ignore invalid inactive rules when saving settings ([b09fbdc](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b09fbdc0f4a966bbb8688b269615b96ba3cf2412))
* **tries:** preserve legacy Custom Start crossing selection ([9debad1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/9debad1240ccf0bc19a673b439cc8cc285a4fb2d))
* **tries:** preserve results starting at zero timestamp ([05f3fa4](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/05f3fa4c4a98849eb95d6449e31299001b53706b))
* **tries:** prevent closing with invalid scoring rules ([9579a58](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/9579a5828f7c8b0bf9bf7dadae2837b52b51f49c))
* **tries:** retain attempt penalties and their explanations ([03264ce](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/03264ce8b200c03993fb8bee5b61e2156c051b46))
* **tries:** show later splits after incomplete attempts ([d064e64](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/d064e647139394b81c5e846e0b07ee5dda21319f))
* **tries:** warn when invalid inactive rules are reset ([8c3fe78](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/8c3fe788a600a7b304d5650db8b9243fddb87aa2))


### Documentation

* **tries:** document scoring and timing contracts for agents ([7dbe2c5](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7dbe2c54b127b374d5386dfef95dd6eafa1e560e))

## [0.5.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.4.1...v0.5.0) (2026-10-15)


### Features

* **stats:** report gaps and sizes of neighbouring participant packs ([48e42e6](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/48e42e6ba38b264f24896bfa6c37d37acc364a83))


### Bug Fixes

* **settings:** bind pack threshold to the absolute statistics checkbox ([1372bbb](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1372bbbe3ce0f38065f5ecaaf02fdddfaf7d1656))
* **settings:** sync pack threshold availability when loading race info ([9ec5660](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/9ec56601b49645526582a85031fe4d047731b1dd))

## [0.4.1](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.4.0...v0.4.1) (2026-10-11)


### Bug Fixes

* resolve runtime files beside the portable application ([7f4a216](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7f4a21678177383683ab9ce6f196f8ad48f61458))


### Documentation

* clarify portable runtime paths for coding agents ([b17bb8d](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/b17bb8d818b320882ce74122e779c2736740967b))

## [0.4.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.3.0...v0.4.0) (2026-10-03)


### Features

* **time-trial:** caption every field on the start board ([73d9da2](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/73d9da21628bd8bdd96217ac21ab586396fb9622))

## [0.3.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.2.0...v0.3.0) (2026-10-03)


### Features

* **config:** ask before saving over a damaged race-info file ([064c789](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/064c789551a509e8ef138bede11fe114616fecd4))
* **config:** report a race-info file whose fields no longer line up ([d58c5db](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/d58c5db2122b75ce98f2aafdcda43e832cc8a7bd))


### Bug Fixes

* **config:** do not judge a key=value race-info file by the positional anchors ([14cf40b](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/14cf40b7e71bb6325dca2f3b18cbd5f7f5f83b7a))
* **config:** fold line breaks out of the config on load, not only on save ([841cb6a](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/841cb6a7e85c56812e6f7fb1b6f849c58e99ed29))
* **config:** keep line breaks out of race-info values so the file cannot shift ([2a485ec](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2a485ec630f4ce78c94a29bb550d32e17baf0ecd))
* **ui:** keep an unreadable save target from raising out of the damaged-file check ([56848ab](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/56848abb25c7825ea6826ddacc611a3dcadc41a9))

## [0.2.0](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.1.9...v0.2.0) (2026-09-15)


### Features

* **ui:** add a time-trial start board window ([7cd82a4](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/7cd82a41e421f8daf3f2abd232681029a0cd49e4))


### Bug Fixes

* **time-trial:** shorten an over-long rider name to its corner ([6666d96](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/6666d96c5988ac630e04c10c103ad3cecde214c5))
* **time-trial:** size board text in pixels so screen DPI cannot rescale it ([9a63c4e](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/9a63c4edd714b00ce0d6a26b394e0b168bb49d71))
* **time-trial:** take the first group entry, matching the protocol ([1ccd756](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1ccd756e6521c344ff2239805820aecc05e98a72))
* **ui:** close the start board on exit so the process can quit ([68eafd5](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/68eafd578fff4b4ce299403b97ac74f1d2f96c98))
* **ui:** restore a minimized start board when the button is pressed again ([95b78fb](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/95b78fbd241f23ed60edadba830bef7675c0e48e))

## [0.1.9](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.1.8...v0.1.9) (2026-09-04)


### Documentation

* require an explicit yes for outward commands and record the UTF-16 trap ([5db45de](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/5db45deba491bf5923e53eb6082b7dba67569e7d))

## [0.1.8](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.1.7...v0.1.8) (2026-08-28)


### Bug Fixes

* **ui:** wait for worker threads on close so a running QThread can't abort exit ([1b66b03](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/1b66b03d0881d4e82919582ed1878bd362466e6a))

## [0.1.7](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.1.6...v0.1.7) (2026-08-22)


### Bug Fixes

* **ui:** persist auto-refresh interval so the checkbox survives restart ([c1aec71](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/c1aec718a00bee8c4da0345f6792e35c89efed54))

## [0.1.6](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.1.5...v0.1.6) (2026-07-27)


### Bug Fixes

* keep the macos bundle file name free of spaces ([bed02bf](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/bed02bf079930b033ff13c83eafbad4dec9b38ea))

## [0.1.5](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.1.4...v0.1.5) (2026-07-27)


### Bug Fixes

* give the macos bundle a proper identifier and version ([cbe36e7](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/cbe36e756d41ee8ee133a8c0e8e146f043eb5ca6))
* show the full app name in the dock and task switcher ([e0a27ac](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/e0a27ac253d0e8954a5413e9a19ebab5b7bb39d7))

## [0.1.4](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.1.3...v0.1.4) (2026-07-25)


### Bug Fixes

* keep uv.lock in step with the released version ([f4fcf27](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/f4fcf274812e8de17d250c5c842f6b0de47dc216))

## [0.1.3](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.1.2...v0.1.3) (2026-07-25)


### Documentation

* explain how to run the app from a release ([2f25e18](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/2f25e18f4d6232dda84ea6c85e0c4cfaf68cc59d))

## [0.1.2](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/compare/v0.1.1...v0.1.2) (2026-07-22)


### Bug Fixes

* embed the app icon in the macOS build ([63c6a41](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/commit/63c6a4188b424726a71e4986851e39600d4d786f))

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
