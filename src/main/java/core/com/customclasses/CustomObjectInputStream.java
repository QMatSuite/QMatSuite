package core.com.customclasses;

import java.io.IOException;
import java.io.InputStream;
import java.io.ObjectInputStream ;
import java.io.ObjectStreamClass;
import java.lang.reflect.Field;

import core.com.error.ShowAlert;

public class CustomObjectInputStream extends ObjectInputStream  {
	public CustomObjectInputStream(InputStream in) throws IOException {
        super(in);
    }

	//to make the serialization backward compatible after package change
	//only allow re-basing the class to "core" package
    @Override
    protected ObjectStreamClass readClassDescriptor() throws IOException, ClassNotFoundException {
        ObjectStreamClass result = super.readClassDescriptor();
        String currentName = result.getName();
        try {
        	Class<?> previousClass = Class.forName(currentName);
        	if(previousClass==null) {
        		throw new ClassNotFoundException("Exception when finding the existinig serializable class.");
        	}
        }catch(ClassNotFoundException eclass) {
        	//ShowAlert.showAlert("Info", "Cannot find class "+currentName+" but "+"core." + currentName);
        	//only handle the case where class is not found
        	try {
        		String newClassName = "core." + currentName;
                // Test the class exists
                Class<?> localClass = Class.forName(newClassName);

                Field nameField = ObjectStreamClass.class.getDeclaredField("name");
                nameField.setAccessible(true);
                nameField.set(result, newClassName);

                ObjectStreamClass localClassDescriptor = ObjectStreamClass.lookup(localClass);
                Field suidField = ObjectStreamClass.class.getDeclaredField("suid");
                suidField.setAccessible(true);
                suidField.set(result, localClassDescriptor.getSerialVersionUID());
            } catch(Exception e) {
            	ShowAlert.showAlert("Error", "Cannot find class "+currentName+" or "+"core." + currentName);
                throw new IOException("Exception when trying to replace namespace", e);
            }
        }
        return result;
    }
}
