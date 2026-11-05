import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import android.os.SystemProperties;
import android.os.ServiceManager;
import android.os.IBinder;
import com.hkmc.factory.IMicomFactoryService.Stub;

public final class NeevConsentTest {
    interface MissingMethod { void differentMethod(); }
    interface WrongReturn { boolean hideConsentScreen(); }
    interface WrongArgs { void hideConsentScreen(int value); }
    static int assertions;
    static String output;

    static void reset() {
        SystemProperties.VALUES.clear();
        SystemProperties.VALUES.put("ro.build.product", NeevConsent.PRODUCT);
        SystemProperties.VALUES.put("ro.mobis.targetdir", NeevConsent.MODEL);
        SystemProperties.VALUES.put("sys.boot_completed", "1");
        ServiceManager.binder = new IBinder() {};
        ServiceManager.lookups = 0;
        ServiceManager.bootCompletedOnLookup = null;
        Stub.calls = 0;
        Stub.error = null;
        com.hkmc.Service.FACTORY_SERVICE = "com.hkmc.factory";
    }

    static int run(String arg) {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        int rc = NeevConsent.run(new String[] {arg}, new PrintStream(bytes));
        output = bytes.toString();
        return rc;
    }

    static void check(boolean ok, String detail) {
        assertions++;
        if (!ok) throw new AssertionError(detail + "\n" + output);
    }

    public static void main(String[] args) throws Exception {
        reset();
        check(run("--dismiss") == 0 && Stub.calls == 1, "dismiss invokes exactly once");
        check(output.contains("status=dismiss-requested"), "must not claim verified UI dismissal");
        reset();
        SystemProperties.VALUES.put("sys.boot_completed", "0");
        check(run("--check") == 0 && Stub.calls == 0, "read-only check can run before boot completion");
        check(output.contains("status=ready"), "check ready status");
        check(run("--dismiss") == 10 && Stub.calls == 0, "boot-incomplete cannot call");
        reset();
        ServiceManager.bootCompletedOnLookup = "0";
        check(run("--dismiss") == 10 && ServiceManager.lookups == 1 && Stub.calls == 0,
                "framework restart during service resolution prevents dismissal");
        check(output.contains("status=boot-incomplete"), "late readiness loss is retryable only before mutation");
        reset();
        ServiceManager.bootCompletedOnLookup = "";
        check(run("--dismiss") == 10 && Stub.calls == 0, "missing readiness after resolution prevents dismissal");
        reset();
        ServiceManager.bootCompletedOnLookup = "0";
        check(run("--check") == 0 && ServiceManager.lookups == 1 && Stub.calls == 0,
                "check mode remains read-only and independent of late boot state");
        reset();
        SystemProperties.VALUES.put("ro.build.product", "NEEV.USA.0000.V039.001.260902");
        check(run("--dismiss") == 20 && ServiceManager.lookups == 0 && Stub.calls == 0, "wrong firmware refused before service lookup");
        reset();
        SystemProperties.VALUES.put("ro.mobis.targetdir", "cvev_kr");
        SystemProperties.VALUES.put("ro.mobis.onebindir", "neev_kr");
        check(run("--dismiss") == 20 && ServiceManager.lookups == 0, "conflicting target cannot be overridden");
        reset();
        SystemProperties.VALUES.put("ro.mobis.onebindir", "other");
        check(run("--dismiss") == 20 && ServiceManager.lookups == 0, "conflicting onebin refused");
        reset();
        SystemProperties.VALUES.remove("ro.mobis.targetdir");
        SystemProperties.VALUES.put("ro.mobis.onebindir", "neev_kr");
        check(run("--check") == 0 && Stub.calls == 0, "observed onebindir property supported");
        reset();
        SystemProperties.VALUES.put("ro.mobis.targetdir", "/system/onebin/neev_kr");
        check(run("--check") == 0 && Stub.calls == 0, "stock absolute target directory supported");
        check(output.contains("targetdir_raw=/system/onebin/neev_kr"), "raw target directory retained for diagnostics");
        reset();
        SystemProperties.VALUES.put("ro.mobis.targetdir", "/system/onebin/neev_kr///");
        SystemProperties.VALUES.put("ro.mobis.onebindir", "/system/onebin/neev_kr/");
        check(run("--check") == 0 && Stub.calls == 0, "matching stock paths with trailing slashes supported");
        check(output.contains("onebindir_raw=/system/onebin/neev_kr/"), "raw onebin retained for diagnostics");
        reset();
        SystemProperties.VALUES.put("ro.mobis.targetdir", "/system/onebin/cvev_kr/");
        SystemProperties.VALUES.put("ro.mobis.onebindir", "/system/onebin/neev_kr/");
        check(run("--dismiss") == 20 && ServiceManager.lookups == 0, "conflicting stock target path refused");
        reset();
        SystemProperties.VALUES.put("ro.mobis.targetdir", "/system/onebin/neev_kr/");
        SystemProperties.VALUES.put("ro.mobis.onebindir", "/system/onebin/cvev_kr/");
        check(run("--dismiss") == 20 && ServiceManager.lookups == 0, "conflicting stock onebin path refused");
        reset();
        SystemProperties.VALUES.put("ro.mobis.targetdir", "/unrelated/neev_kr/");
        SystemProperties.VALUES.put("ro.mobis.onebindir", "neev_kr");
        check(run("--dismiss") == 20 && ServiceManager.lookups == 0, "unrelated path cannot claim model by basename");
        reset();
        SystemProperties.VALUES.put("ro.mobis.targetdir", "/system/onebin/../onebin/neev_kr");
        check(run("--dismiss") == 20 && ServiceManager.lookups == 0, "path traversal is not a model identity");
        reset();
        ServiceManager.binder = null;
        check(run("--dismiss") == 11 && Stub.calls == 0, "service not registered returns retryable readiness status only");
        reset();
        Stub.error = new IllegalStateException("Cannot broadcast before boot completed");
        check(run("--dismiss") == 21 && Stub.calls == 1, "call exception is not blindly retried");
        check(output.contains("java.lang.IllegalStateException") && output.contains("status=error"), "unwrap reflection exception");
        reset();
        com.hkmc.Service.FACTORY_SERVICE = "different";
        check(run("--dismiss") == 20 && ServiceManager.lookups == 0, "factory registration name verified");
        reset();
        check(run("unknown") == 20 && Stub.calls == 0, "invalid args cannot invoke");
        for (Class<?> c : new Class<?>[] {MissingMethod.class, WrongReturn.class, WrongArgs.class}) {
            boolean rejected = false;
            try { NeevConsent.validateInterface(c); } catch (NoSuchMethodException expected) { rejected = true; }
            check(rejected, "missing or changed method refused: " + c.getName());
        }
        File temp = File.createTempFile("neev-consent-test-", ".dir");
        if (!temp.delete() || !temp.mkdir()) throw new AssertionError("temp directory");
        try {
            check(NeevConsent.resolveModel("", "", temp).equals(""), "missing model stays unknown");
            File neev = new File(temp, "neev_kr");
            if (!neev.mkdir()) throw new AssertionError("neev directory");
            check(NeevConsent.resolveModel("", "", temp).equals("neev_kr"), "single onebin directory supported");
            File other = new File(temp, "cvev_kr");
            if (!other.mkdir()) throw new AssertionError("other directory");
            check(NeevConsent.resolveModel("", "", temp).equals("ambiguous-onebin"), "multi-model directory cannot imply active model");
            other.delete(); neev.delete();
        } finally { temp.delete(); }
        System.out.println("PASS: " + assertions + " assertions (host reflection fakes; no vehicle validation)");
    }
}
