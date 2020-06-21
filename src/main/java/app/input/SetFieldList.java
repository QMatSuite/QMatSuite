package app.input;

import java.util.ArrayList;

import com.consts.Constants.EnumInProgram;
import com.consts.Constants.EnumStep;

import agent.WrapperBoolean;
import agent.WrapperDouble;
import agent.WrapperEnum;
import agent.WrapperInteger;
import javafx.scene.control.Alert;
import javafx.scene.control.ComboBox;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import main.MainClass;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.CheckBox;

public class SetFieldList {
	
	private ArrayList<ComboBox<?>> comboList;
	private ArrayList<String> wrapperEnumList;
	private ArrayList<CheckBox> checkEnumList;
	
	private ArrayList<ToggleButton> toggleList;
	private ArrayList<String> wrapperBooleanList;
	private ArrayList<CheckBox> checkBooleanList;
	
	private ArrayList<TextField> textIntegerList;
	private ArrayList<String> wrapperIntegerList;
	private ArrayList<CheckBox> checkIntegerList;
	
	private ArrayList<TextField> textDoubleList;
	private ArrayList<String> wrapperDoubleList;
	private ArrayList<CheckBox> checkDoubleList;
	
	private MainClass mainClass;
	
	private EnumStep enumStep;
	
	public SetFieldList(MainClass mc, EnumStep es) {
		mainClass = mc;
		enumStep = es;
		comboList = new ArrayList<ComboBox<?>>();
		wrapperEnumList = new ArrayList<String>();
		checkEnumList = new ArrayList<CheckBox>();
		toggleList = new ArrayList<ToggleButton>();
		wrapperBooleanList = new ArrayList<String>();
		checkBooleanList = new ArrayList<CheckBox>();
		textIntegerList = new ArrayList<TextField>();
		wrapperIntegerList = new ArrayList<String>();
		checkIntegerList = new ArrayList<CheckBox>();
		textDoubleList = new ArrayList<TextField>();
		wrapperDoubleList =  new ArrayList<String>();
		checkDoubleList = new ArrayList<CheckBox>();
	}
	public <T extends EnumInProgram> void addEnumPair(ComboBox<T> cb, String we, CheckBox checkB) {
		comboList.add(cb);wrapperEnumList.add(we);checkEnumList.add(checkB);
	}
	public void addBoolPair(ToggleButton tb, String wb, CheckBox checkB) {
		toggleList.add(tb);wrapperBooleanList.add(wb);checkBooleanList.add(checkB);
	}
	public void addIntPair(TextField tf, String wi, CheckBox checkB) {
		textIntegerList.add(tf);wrapperIntegerList.add(wi);checkIntegerList.add(checkB);
	}
	public void addDoublePair(TextField tf, String wd, CheckBox checkB) {
		textDoubleList.add(tf);wrapperDoubleList.add(wd);checkDoubleList.add(checkB);
	}
	public void setAllFields() {
		try {
			for(int i=0;i<comboList.size();i++) {	
				Object obj = mainClass.projectManager.getObject(wrapperEnumList.get(i), enumStep);
				InputController.setCombo(comboList.get(i), (WrapperEnum) obj);	
				InputController.setCheck(checkEnumList.get(i), !((WrapperEnum) obj).isEnabled());
			}
			for(int i=0;i<toggleList.size();i++) {
				Object obj = mainClass.projectManager.getObject(wrapperBooleanList.get(i), enumStep);
				InputController.setToggle(toggleList.get(i), (WrapperBoolean) obj);
				InputController.setCheck(checkBooleanList.get(i), !((WrapperBoolean) obj).isEnabled());
			}
			for(int i=0;i<textIntegerList.size();i++) {
				Object obj = mainClass.projectManager.getObject(wrapperIntegerList.get(i), enumStep);
				InputController.setField(textIntegerList.get(i), (WrapperInteger) obj);
				InputController.setCheck(checkIntegerList.get(i), !((WrapperInteger) obj).isEnabled());
			}
			for(int i=0;i<textDoubleList.size();i++) {
				Object obj = mainClass.projectManager.getObject(wrapperDoubleList.get(i), enumStep);
				InputController.setField(textDoubleList.get(i), (WrapperDouble) obj);
				InputController.setCheck(checkDoubleList.get(i), !((WrapperDouble) obj).isEnabled());
			}
		} catch (Exception e) {
			Alert alert1 = new Alert(AlertType.ERROR);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Fail to cast! "+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
		}
	}
}
