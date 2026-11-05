아이오닉 5 NEEV KOR 260902 시작 안내창 자동 닫기 — 4.3.1

대상 차량
현대 아이오닉 5, NEEV.KOR.0000.V039.001.260902
Android 4.4.2 / tcc803x / NEMESIS 설치 차량
HMG-API 설치 여부와 무관하게 동작하도록 만든 독립 NEMESIS 패키지입니다.
차량·펌웨어와 API 조건이 맞지 않으면 안내창 닫기를 실행하지 않습니다.

설치
1. NEEV_260902_STARTUP_NOTICE_v4.3.1_USB.zip의 압축을 풉니다.
2. FAT32 또는 exFAT USB의 최상위에 아래 파일과 폴더를 넣습니다.
   NEMESIS.data
   NEMESIS.sh
   local.hkmc.factory82-4.3.1-neev.zip
   NEEV_STARTUP_NOTICE/ 폴더
   안쪽 패키지 ZIP은 압축을 풀지 않습니다.
3. 주차한 상태에서 헤드유닛이 켜진 뒤 USB를 연결합니다.
4. NEMESIS의 실행 요청을 승인하면 사전 검사 후 패키지를 설치합니다.
   설치 완료 후 USB를 분리하고,
   다음 시동·헤드유닛 기동에서 시작 안내창이 닫히는지 확인합니다.

USB 최상위에 다른 설치용 NEMESIS.data가 있으면 먼저 보관하세요.
이 패키지와 제거용 USB 파일을 동시에 복사하지 마세요.
기존 local.hkmc.factory82 4.2와 패키지 ID가 같으므로 기존 버전을 교체합니다.
NEMESIS 자체나 HMG-API, CarPlay 패키지는 이 설치본에 포함하지 않습니다.

4.3.1 설치 오류 수정
정상 모델 경로 /system/onebin/neev_kr/를 neev_kr로 인식합니다.
차량에 없을 수 있는 dirname/tail 명령 의존성을 제거했습니다.
새 설치기는 원본 패키지를 교체하기 전에 API 사전 검사를 완료합니다.
실패 시 USB의 NEEV_STARTUP_NOTICE_RESULT_날짜_번호 폴더에
INSTALL.log, PREFLIGHT.txt(검사 실행 시), STATUS.txt가 남습니다.
NEEV_STARTUP_NOTICE_LAST_RESULT.txt에는 마지막 결과 폴더가 기록됩니다.
오류가 다시 나오면 USB를 컴퓨터에 다시 연결하여 이 로그를 확인하세요.

동작
원본 패키지의 번호 82 직접 호출을 차량에서 확인된
com.hkmc.factory.IMicomFactoryService.hideConsentScreen() 이름 호출로 바꿨습니다.
실차 보고서에서 확인된 서비스 인터페이스와 메서드를 실행 전에 검사합니다.
Android 부팅 완료를 확인한 뒤 시작 안내창 닫기를 요청하며,
계속 반복해서 누르는 대신 기동·화면 복귀 감지에 따라 처리합니다.
자동차의 주행 제어나 일반 경고창을 대상으로 하지 않습니다.

확인 상태
차량 보고서로 대상 차량 정보와 API 존재를 확인했습니다.
이 수정본의 실제 차량 설치 및 안내창 자동 닫기 성공은 아직 확인하지 않았습니다.
호스트 검사 결과는 함께 제공된 HOST_TEST_RESULTS.txt와 BUILD_RESULT.json에 있습니다.
검사 성공은 실제 차량에서 안내창이 닫혔다는 뜻이 아닙니다.
실차 결과를 확인하기 전에는 동작 검증 완료 버전으로 취급하지 마세요.

문제가 있을 때
USB를 연결한 상태에서 NEMESIS의 이 패키지 앱을 실행하면 읽기 전용 진단을 합니다.
인식 가능한 USB 경로가 있으면 NEEV-STARTUP-NOTICE/diagnostics.txt에 저장합니다.
이 파일에는 차량·부팅 상태, API 검사, 서비스 상태와 최근 모니터 기록이 들어갑니다.
저장 경로가 없으면 진단 출력만 표시됩니다.

제거
NEEV_260902_STARTUP_NOTICE_v4.3.1_REMOVE_USB.zip을 별도로 압축 해제하고,
안의 NEMESIS.data와 NEMESIS.sh를 USB 최상위에 넣은 뒤 연결합니다.
또는 NEMESIS의 패키지 관리에서 local.hkmc.factory82를 제거합니다.
제거는 이후 자동 호출을 멈춥니다. 이미 닫힌 안내창을 다시 표시하거나
문서화되지 않은 OEM 호출의 효과를 되돌리는 역호출은 알려져 있지 않습니다.

개발용 파일
local.hkmc.factory82-4.3.1-neev.zip: NEMESIS 설치 패키지
NEEV_260902_STARTUP_NOTICE_v4.3.1_USB.zip: 설치용 USB 묶음
NEEV_260902_STARTUP_NOTICE_v4.3.1_REMOVE_USB.zip: 제거용 USB 묶음
NEEV_260902_STARTUP_NOTICE_v4.3.1_SOURCE.zip: 소스·검사·빌드 스크립트
evidence.json: 차량 근거, 원본 해시, API와 한계
SHA256SUMS.txt: 배포 파일 체크섬

재빌드: 작업 폴더에서 python3 neev-startup-notice/build.py
기본 도구: .tools/java-build의 JDK 17과 r8.jar (D8, Android 최소 API 19)
다른 위치의 도구는 --jdk 및 --r8 옵션으로 지정할 수 있습니다.
빌드 스크립트는 PC 검사와 파일 패키징만 실행하며 차량 코드를 실행하지 않습니다.

원본 패키지
local.hkmc.factory82 4.2
https://github.com/armandodollia/nemesis-package-builds
SHA-256: c9d12d19fbccbcfd4d0c0e537ae692dfa0a8eba82ae6d21d05181627b1e810bb
원본 동작 방식을 바탕으로 NEEV 차량용 실행부와 설치 구성을 수정했습니다.
