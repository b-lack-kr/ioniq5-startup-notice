import java.io.File;
import java.io.PrintStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;

/** Firmware-specific startup notice request. No numeric Binder transaction. */
public final class NeevConsent {
    static final String PRODUCT = "NEEV.KOR.0000.V039.001.260902";
    static final String MODEL = "neev_kr";
    static final String SERVICE = "com.hkmc.factory";

    private NeevConsent() {}

    public static void main(String[] args) {
        System.exit(run(args, System.out));
    }

    static int run(String[] args, PrintStream out) {
        if (args.length != 1 || !("--check".equals(args[0]) || "--dismiss".equals(args[0]))) {
            return result(out, "refused", "usage: NeevConsent --check|--dismiss", 20);
        }
        boolean dismiss = "--dismiss".equals(args[0]);
        try {
            String product = property("ro.build.product");
            String target = property("ro.mobis.targetdir");
            String onebin = property("ro.mobis.onebindir");
            String model = resolveModel(target, onebin, new File("/system/onebin"));
            out.println("product=" + clean(product));
            out.println("targetdir_raw=" + clean(target));
            out.println("onebindir_raw=" + clean(onebin));
            out.println("model=" + clean(model));
            if (!PRODUCT.equals(product) || !MODEL.equals(model)) {
                return result(out, "refused", "head unit does not match the inspected NEEV KOR 260902 firmware", 20);
            }
            String boot = property("sys.boot_completed");
            out.println("boot_completed=" + clean(boot));
            if (dismiss && !"1".equals(boot)) {
                return result(out, "boot-incomplete", "waiting for sys.boot_completed=1; no call made", 10);
            }

            Class<?> binderClass = Class.forName("android.os.IBinder");
            Class<?> iface = Class.forName("com.hkmc.factory.IMicomFactoryService");
            Class<?> stub = Class.forName("com.hkmc.factory.IMicomFactoryService$Stub");
            Method hide = validateInterface(iface);
            Method asInterface = stub.getMethod("asInterface", binderClass);
            if (!Modifier.isStatic(asInterface.getModifiers())
                    || !iface.isAssignableFrom(asInterface.getReturnType())) {
                return result(out, "refused", "unexpected factory Stub.asInterface signature", 20);
            }
            Object serviceName = Class.forName("com.hkmc.Service").getField("FACTORY_SERVICE").get(null);
            if (!SERVICE.equals(serviceName)) {
                return result(out, "refused", "unexpected factory service registration name", 20);
            }
            Method getService = Class.forName("android.os.ServiceManager").getMethod("getService", String.class);
            Object binder = getService.invoke(null, SERVICE);
            if (binder == null) {
                return result(out, "service-unavailable", "factory service has not registered; no call made", 11);
            }
            if (!binderClass.isInstance(binder)) {
                return result(out, "refused", "factory service is not an IBinder", 20);
            }
            Object factory = asInterface.invoke(null, binder);
            if (!iface.isInstance(factory)) {
                return result(out, "refused", "factory interface could not be resolved", 20);
            }
            out.println("method=com.hkmc.factory.IMicomFactoryService.hideConsentScreen()");
            if (!dismiss) {
                return result(out, "ready", "interface and service available; no dismissal requested", 0);
            }
            // Invoke the public interface method, not a possibly inaccessible Proxy class.
            // The firmware's own Stub selects the correct Binder transaction.
            try {
                hide.invoke(factory);
            } catch (InvocationTargetException e) {
                return result(out, "error", "dismissal exception; do not retry blindly: " + describe(e.getCause()), 21);
            } catch (Throwable e) {
                return result(out, "error", "dismissal outcome unknown; do not retry blindly: " + describe(e), 21);
            }
            return result(out, "dismiss-requested", "method returned; visual dismissal must be verified on the vehicle", 0);
        } catch (Throwable e) {
            return result(out, "refused", "compatibility check failed; no dismissal requested: " + describe(e), 20);
        }
    }

    static Method validateInterface(Class<?> iface) throws NoSuchMethodException {
        Method hide = iface.getMethod("hideConsentScreen");
        if (!iface.isInterface() || hide.getReturnType() != Void.TYPE
                || Modifier.isStatic(hide.getModifiers())) {
            throw new NoSuchMethodException("expected an interface void hideConsentScreen()");
        }
        return hide;
    }

    static String resolveModel(String target, String onebin, File root) {
        target = normalizeModel(target);
        onebin = normalizeModel(onebin);
        // Refuse conflicting properties; never let a matching directory override them.
        if (target.length() != 0 && !MODEL.equals(target)) return target;
        if (onebin.length() != 0 && !MODEL.equals(onebin)) return onebin;
        if (MODEL.equals(target) || MODEL.equals(onebin)) return MODEL;
        // NEMESIS also supports units which expose the model only as a onebin directory.
        File[] children = root.listFiles();
        String only = "";
        if (children != null) {
            for (File child : children) {
                if (!child.isDirectory() || child.getName().startsWith(".")) continue;
                if (only.length() != 0) return "ambiguous-onebin";
                only = child.getName();
            }
        }
        return only;
    }

    private static String normalizeModel(String value) {
        // Native NEMESIS accepts targetdir as a path. Only the known stock path
        // is equivalent here; arbitrary paths ending in neev_kr remain refused.
        while (value.length() > 1 && value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return ("/system/onebin/" + MODEL).equals(value) ? MODEL : value;
    }

    private static String property(String key) throws Exception {
        Method get = Class.forName("android.os.SystemProperties").getMethod("get", String.class);
        Object value = get.invoke(null, key);
        return value instanceof String ? (String) value : "";
    }

    private static int result(PrintStream out, String status, String detail, int code) {
        out.println("status=" + status);
        out.println("detail=" + clean(detail));
        return code;
    }

    private static String describe(Throwable t) {
        if (t == null) return "unknown";
        return t.getClass().getName() + ": " + String.valueOf(t.getMessage());
    }

    private static String clean(String text) {
        return text.replace('\r', ' ').replace('\n', ' ');
    }
}
