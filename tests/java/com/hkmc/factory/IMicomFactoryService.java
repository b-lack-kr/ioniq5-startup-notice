package com.hkmc.factory;
import android.os.IBinder;
public interface IMicomFactoryService {
    void hideConsentScreen();
    public static class Stub {
        public static int calls;
        public static RuntimeException error;
        public static IMicomFactoryService asInterface(IBinder binder) {
            return new IMicomFactoryService() {
                public void hideConsentScreen() { calls++; if (error != null) throw error; }
            };
        }
    }
}
