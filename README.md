# 아이오닉 5 시작 안내창 자동 닫기

**by blackr** · NEMESIS 패키지 · [v4.3.2 시험 배포](https://github.com/b-lack-kr/ioniq5-startup-notice/releases/tag/v4.3.2)

한국형 아이오닉 5의 시작 안내창을 부팅 준비가 끝난 뒤 자동으로 닫도록 요청합니다. **안내창이 아예 나타나지 않게 하는 패치는 아닙니다.** 부팅과 서비스 준비를 기다리는 동안 안내창이 보일 수 있습니다.

v4.3.2의 실제 차량 설치와 안내창 닫기 성공은 아직 확인하지 않았습니다. 차량 보고서에서 필요한 API의 존재를 확인했고, PC에서 동작 검사를 통과한 시험 배포입니다. OEM 호출이 동의 상태를 저장하는지, 그 상태가 다음 기동에도 유지되는지는 확인되지 않았습니다.

## 지원 대상

| 항목 | 대상 |
| --- | --- |
| 차량 | 현대 아이오닉 5, NEEV KOR |
| 펌웨어 | `NEEV.KOR.0000.V039.001.260902` |
| Android / 플랫폼 | `4.4.2` / `tcc803x` |
| 모델 폴더 | `neev_kr` |
| 사전 조건 | NEMESIS가 설치된 헤드유닛 |

이 펌웨어만 대상으로 합니다. 다른 차량·지역·펌웨어의 호환성은 확인하지 않았으며, 대상 정보가 다르면 실행을 거부합니다. HMG-API는 필요하지 않습니다.

## 설치

1. [설치용 USB ZIP 다운로드](https://github.com/b-lack-kr/ioniq5-startup-notice/releases/download/v4.3.2/NEEV_260902_STARTUP_NOTICE_v4.3.2_USB.zip)
2. 바깥 ZIP의 압축을 풀고, FAT32 또는 exFAT USB의 최상위에 다음 항목을 복사합니다.

   ```text
   NEMESIS.data
   NEMESIS.sh
   local.hkmc.factory82-4.3.2-neev.zip
   NEEV_STARTUP_NOTICE/
   ```

   안쪽 `local.hkmc.factory82-4.3.2-neev.zip`은 압축을 풀지 않습니다. USB에 기존 `NEMESIS.data`가 있다면 먼저 보관하세요.
3. 주차한 상태에서 헤드유닛을 켠 뒤 USB를 연결하고, NEMESIS의 **실행 요청**을 승인합니다.
4. 설치기는 차량·파일·API를 검사한 후 패키지를 설치합니다. 완료를 확인하고 USB를 분리한 뒤, 다음 시동·헤드유닛 기동에서 안내창이 닫히는지 확인합니다.

패키지 ID는 `local.hkmc.factory82`입니다. 같은 ID의 원본 4.2 또는 이전 수정본이 설치되어 있으면 교체합니다. NEMESIS 자체나 HMG-API, CarPlay 패키지를 설치·수정하는 작업은 포함하지 않습니다.

## 설치 결과와 진단

설치 결과는 USB에 저장됩니다.

```text
NEEV_STARTUP_NOTICE_LAST_RESULT.txt
NEEV_STARTUP_NOTICE_RESULT_날짜_번호/
  STATUS.txt
  INSTALL.log
  PREFLIGHT.txt    # API 검사를 실행한 경우
```

`INSTALLED_TEST_NEXT_START`는 설치 완료를 뜻하며, 실제 화면이 닫혔다는 뜻은 아닙니다. 실패하면 `STATUS.txt`와 `INSTALL.log`를 확인하세요.

설치 후에는 USB를 연결하고 NEMESIS에서 이 패키지 앱을 실행하면 읽기 전용 진단을 할 수 있습니다. 지원되는 USB 경로가 있으면 `NEEV-STARTUP-NOTICE/diagnostics.txt`에 차량·부팅 상태, API 검사, 서비스 상태와 모니터 기록을 저장합니다. 저장 경로가 없으면 진단 출력만 표시됩니다.

문제를 보고할 때는 [Issues](https://github.com/b-lack-kr/ioniq5-startup-notice/issues)에 펌웨어, 패키지 버전, 실패 단계와 관련 로그 부분을 남겨주세요. 전체 차량 보고서는 필요하지 않습니다. 로그를 공개하기 전에는 개인 식별 정보가 포함되어 있는지 확인하세요.

## 제거

[제거용 USB ZIP](https://github.com/b-lack-kr/ioniq5-startup-notice/releases/download/v4.3.2/NEEV_260902_STARTUP_NOTICE_v4.3.2_REMOVE_USB.zip)의 압축을 풀고, `NEMESIS.data`와 `NEMESIS.sh`를 USB 최상위에 복사한 뒤 차량에서 실행합니다. 설치용 파일과 제거용 파일을 동시에 사용하지 마세요.

NEMESIS의 패키지 관리에서 `local.hkmc.factory82`를 제거해도 됩니다. 제거하면 이후 자동 호출이 중단됩니다. 이미 닫힌 안내창을 다시 표시하거나 OEM 호출의 효과를 되돌리는 역호출은 알려져 있지 않습니다.

## 동작과 확인 범위

원본의 Binder 번호 `82` 직접 호출 대신, 차량의 `com.hkmc.factory.IMicomFactoryService.hideConsentScreen()` 메서드를 이름으로 확인하여 호출합니다. 실제 Binder 번호는 차량의 인터페이스 구현이 선택합니다.

모니터는 부팅 완료(`sys.boot_completed=1`), 화면 상태와 서비스 등록 상태를 1초 간격으로 확인합니다. 조건이 충족되면 별도의 고정 대기 없이 검증과 닫기를 한 번의 Java 실행에서 처리합니다. 호출 직전 부팅 상태도 다시 확인합니다. 실제 반응에는 상태 확인 주기, 프로그램 실행과 OEM 처리 시간이 더해지므로 화면이 나타나는 순간 바로 사라진다고 보장하지는 않습니다.

v4.3.2에서 기존의 부팅 후 최소 15초 조건과 추가 2초 대기를 제거했습니다. 준비되지 않은 서비스는 화면과 부팅이 준비된 시점부터 최대 120초 동안 확인합니다. 성공 또는 결과가 불확실한 호출은 같은 기동에서 무작정 반복하지 않으며, 빠른 화면 복귀·프레임워크 재시작은 중복 억제 때문에 누락되지 않도록 처리합니다. API가 정상 반환해도 실제 화면 변화까지 확인된 것은 아닙니다. 일반 경고창이나 차량 주행 제어를 대상으로 하지 않습니다.

v4.3.0은 차량에서 설치 승인 직후 실패가 보고됐고, 실패 로그가 없어 원인을 확정하지 못했습니다. v4.3.1에서 모델 폴더 경로 처리, `dirname`·`tail` 명령 의존성과 설치 로그 수집을 수정했습니다. 기존 패키지를 교체하기 전에 API 사전 검사를 수행합니다. v4.3.1 사용자는 안내창이 늦게 닫힌다고 보고했으며, v4.3.2는 그 지연을 줄이기 위한 버전입니다. 새 버전의 실차 지연 시간은 아직 측정하지 않았습니다.

PC 검사 결과:

- Java API·모델 검사: 32개 assertion 통과
- 실제 셸 모니터를 격리된 가짜 명령으로 검사: 31개 시나리오 통과
- USB 설치기 검사: 14개 시나리오 통과

이 검사는 실차 검증을 대신하지 않습니다. 공개 저장소에는 원본 차량 보고서나 개인 USB 배포 기록을 포함하지 않습니다.

## 소스에서 빌드

macOS 또는 Linux에서 Python 3, JDK 17, D8을 포함한 `r8.jar`가 필요합니다.

```sh
python3 build.py --jdk /path/to/jdk17 --r8 /path/to/r8.jar
```

검사 후 Android 최소 API 19용 DEX와 설치·제거·소스 ZIP을 만들며, 결과는 저장소의 `dist/`와 `release/`에 저장됩니다. 빌드 과정에서는 차량에 접속하거나 차량 명령을 실행하지 않습니다. 테스트의 Android/OEM 가짜 클래스는 배포용 JAR에 포함하지 않습니다.

## 출처와 라이선스

blackr의 NEEV KOR 전용 수정본입니다. armandodollia의 [Factory82 원본 패키지](https://github.com/armandodollia/nemesis-package-builds) 4.2를 바탕으로 만들었습니다.

MIT 라이선스이며, 원저작자의 저작권 및 사용 허가 고지를 유지합니다. 자세한 내용은 [LICENSE](LICENSE)와 [package/NOTICE.txt](package/NOTICE.txt)를 참고하세요.
