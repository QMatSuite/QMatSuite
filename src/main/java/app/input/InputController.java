/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.input;


import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.Initializable;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import javafx.scene.control.Tooltip;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.Label;
import javafx.scene.control.RadioButton;
import main.MainClass;
import agent.WrapperBoolean;
import agent.WrapperDouble;
import agent.WrapperEnum;
import agent.WrapperInteger;
import com.consts.QeDocumentation;
import com.consts.Constants.EnumInProgram;
import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumStep;

public abstract class InputController implements Initializable{
	
	protected MainClass mainClass;
	private Label statusTextField;//if existed, provides status information
	protected boolean allDefault;//whether all set to default
	protected SetFieldList setFieldList;
	protected final EnumStep enumStep;
	
	protected InputController(MainClass mc, EnumStep es) {
		mainClass = mc;
		allDefault = false;
		setFieldList = new SetFieldList(mc,es);
		enumStep = es;
	}
	protected void loadProjectParameters() {
		setFieldList.setAllFields();
	}
	protected void initParameterSet(ToggleButton tb, String fieldName, String onText, String offText, CheckBox checkReset, Button buttonInfo, String infoKey, CheckBox checkResetAll) {
		initParameterSet(tb, fieldName, onText, offText, checkReset, buttonInfo, checkResetAll);
		setInfoButton(buttonInfo,infoKey);
	}
	protected void initParameterSet(ToggleButton tb, String fieldName, String onText, String offText, CheckBox checkReset, Button buttonInfo, CheckBox checkResetAll) {
		//GUI->agent
		setToggleListener(tb, fieldName, onText, offText);
		//agent->GUI, loadParameters
		setFieldList.addBoolPair(tb, fieldName, checkReset);
		//reset
		resetToggleListener(checkReset, tb, fieldName, checkResetAll);
	}
	protected <T extends EnumInProgram> void initParameterSet(ComboBox<T> cb, String fieldName, T[] lstEnum, 
			CheckBox checkReset, Button buttonInfo, CheckBox checkResetAll) {
		//default to false: use QE default!
		initParameterSet(cb, fieldName, lstEnum, false, checkReset, buttonInfo, checkResetAll);
	}
	protected <T extends EnumInProgram> void initParameterSet(ComboBox<T> cb, String fieldName, T[] lstEnum, 
			boolean notQEDefault, CheckBox checkReset, Button buttonInfo, CheckBox checkResetAll) {
		//GUI->agent
		setComboListener(cb, lstEnum, fieldName);
		//agent->GUI, loadParameters
		setFieldList.addEnumPair(cb, fieldName, checkReset);
		//reset
		resetComboBoxListener(checkReset, cb, fieldName, checkResetAll, notQEDefault);
	}
	protected void initIntegerParameterSet(TextField tf, String fieldName, EnumNumCondition cond, String nullString, CheckBox checkReset, Button buttonInfo, CheckBox checkResetAll) {
		//GUI->agent
		setIntegerFieldListener(tf, fieldName, cond);
		//agent->GUI, loadParameters
		setFieldList.addIntPair(tf, fieldName, checkReset);
		//reset
		resetTextFieldIntegerListener(checkReset, tf, fieldName, checkResetAll, nullString);
	}
	protected void initDoubleParameterSet(TextField tf, String fieldName, EnumNumCondition cond, String nullString, CheckBox checkReset, Button buttonInfo, CheckBox checkResetAll) {
		//GUI->agent
		setDoubleFieldListener(tf, fieldName, cond);
		//agent->GUI, loadParameters
		setFieldList.addDoublePair(tf, fieldName, checkReset);
		//reset
		resetTextFieldDoubleListener(checkReset, tf, fieldName, checkResetAll, nullString);
	}
	protected void setPointerStatusTextField(Label lb) {
		statusTextField = lb;
	}
	protected void setToggleListener(ToggleButton tb, String fieldName, String onText, String offText) {	
		//tb is also compatible with RadioButton
		if(enumStep==null || tb==null) {
    		Alert alert1 = new Alert(AlertType.ERROR);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Cannot set listener! EnumStep is null or on/off text is null. Abort..");
	    	alert1.showAndWait();
	    	return;
    	}
		//take care of the starting of the program
		if(onText!=null && offText!=null) {
			if(tb.isSelected()) {tb.setText(onText);}
			else {tb.setText(offText);}
		}
		
		tb.selectedProperty().addListener((observable, oldValue, newValue) -> {
			if(newValue==null) return;
			if(onText!=null && offText!=null) {
				if(newValue) {tb.setText(onText);}
				else {tb.setText(offText);}
			}
			Object obj = mainClass.projectManager.getObject(fieldName, enumStep);
			if(obj==null) return;
			try {
				if(statusTextField!=null) {statusTextField.setText("");}
				((WrapperBoolean) obj).setValue(newValue);
				//if(EnumStep.GEO.equals(es)) {mainClass.projectManager.updateViewerPlot();}//update the plot if it is geo
			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Fail to cast! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
		});
    }
	protected void setIntegerFieldListener(TextField tf, String fieldName, EnumNumCondition cond) {	
		setFieldListener(tf, fieldName, cond, "int");
    }
	protected void setDoubleFieldListener(TextField tf, String fieldName, EnumNumCondition cond) {	
		setFieldListener(tf, fieldName, cond, "double");
	}
	private void setFieldListener(TextField tf, String fieldName, EnumNumCondition cond, String type) {	
		//type == "int"
		//type == "double"
		if(enumStep==null) {
    		Alert alert1 = new Alert(AlertType.ERROR);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Cannot set listener! EnumStep is null. Abort..");
	    	alert1.showAndWait();
	    	return;
    	}
		tf.textProperty().addListener((observable, oldValue, newValue) -> {
			if(newValue==null) return;
			Object obj = mainClass.projectManager.getObject(fieldName, enumStep);
			if(obj==null) return;
			try {
				if("double".equals(type)) {
					Double tmp = str2double(newValue);
					if (tmp!=null) {
						switch(cond) {
							case no:{break;}
							case positive:
								if(tmp<=0) {
									if(statusTextField!=null) {statusTextField.setText("Must be positive! Set to null.");}
									((WrapperDouble) obj).setValue(null);
									return;
								} 
								break;
							case nonNegative:
								if(tmp<0) {
									if(statusTextField!=null) {statusTextField.setText("Must not be negative! Set to null.");}
									((WrapperDouble) obj).setValue(null);
									return;
								} 
								break;
							default:
								break;
						}
						if(statusTextField!=null) {statusTextField.setText("");}
						((WrapperDouble) obj).setValue(tmp);
						
					}
					else {
						((WrapperDouble) obj).setValue(null);
						return;
					}
				}
				else if("int".equals(type)) {
					Integer tmp = str2int(newValue);
					if (tmp!=null) {
						switch(cond) {
							case no:{break;}
							case positive:
								if(tmp<=0) {
									if(statusTextField!=null) {statusTextField.setText("Must be positive! Set to null.");}
									((WrapperInteger) obj).setValue(null);
									return;
								} 
								break;
							case nonNegative:
								if(tmp<0) {
									if(statusTextField!=null) {statusTextField.setText("Must not be negative! Set to null.");}
									((WrapperInteger) obj).setValue(null);
									return;
								} 
								break;
							default:
								break;
						}
						if(statusTextField!=null) {statusTextField.setText("");}
						((WrapperInteger) obj).setValue(tmp);
					}
					else {
						if(statusTextField!=null) {
							statusTextField.setText(
									statusTextField.getText()==null? "Null input. Set to null.":statusTextField.getText()+" Set to null.");
						}
						((WrapperInteger) obj).setValue(null);
						return;
					}
				}
				else {
					Alert alert1 = new Alert(AlertType.ERROR);
			    	alert1.setTitle("Error");
			    	alert1.setContentText("Unimplemented type detected in InputController!");
			    	alert1.showAndWait();
			    	return;
				}
				if(EnumStep.GEO.equals(enumStep)) {mainClass.projectManager.updateViewerPlot();}//update the plot if it is geo
				if(statusTextField!=null) {statusTextField.setText("");}
			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Fail to cast! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
		});
    }
	protected <T extends EnumInProgram> void setComboListener(ComboBox<T> cb, T[] lstEnum, String fieldName) {	
		if(enumStep==null) {
    		Alert alert1 = new Alert(AlertType.ERROR);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Cannot set listener! EnumStep is null. Abort..");
	    	alert1.showAndWait();
	    	return;
    	}
		ObservableList<T> mixi = FXCollections.observableArrayList(lstEnum);
		cb.setItems(mixi);
		cb.getSelectionModel().selectedItemProperty().addListener((observable, oldValue, newValue) -> {
			if(newValue==null) return;
			Object obj = mainClass.projectManager.getObject(fieldName, enumStep);
			if(obj==null) return;
			try {
				if(statusTextField!=null) {statusTextField.setText("");}
				((WrapperEnum) obj).setValue((EnumInProgram) newValue);
				if(EnumStep.GEO.equals(enumStep)) {mainClass.projectManager.updateViewerPlot();}//update the plot if it is geo
			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Fail to cast! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
		});
    }
	
	protected void resetToggleListener(CheckBox cbResetToggle, ToggleButton toggle, String fieldName, CheckBox cbResetAll) {
		if(cbResetToggle==null) {return;}
		
		cbResetToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue==null) return;
			Object obj = mainClass.projectManager.getObject(fieldName, enumStep);
			if(obj==null) return;
			try {
				WrapperBoolean wb = (WrapperBoolean) obj;
				if (newValue) {
					toggle.setSelected(wb.resetDefault());
					toggle.setDisable(true);
					wb.setEnabled(false);
				}//****not so efficient, double executing
				else {
					toggle.setDisable(false);
					wb.setEnabled(true);
					if(cbResetAll!=null && cbResetAll.isSelected()) {allDefault=false;cbResetAll.setSelected(false);}
				}
			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Fail to cast! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
		});
	}
	protected void resetTextFieldIntegerListener(CheckBox cbResetToggle, TextField tf, String fieldName, CheckBox cbResetAll) {
		resetTextFieldIntegerListener(cbResetToggle, tf, fieldName, cbResetAll, "");
	}
	protected void resetTextFieldIntegerListener(CheckBox cbResetToggle, TextField tf, String fieldName, CheckBox cbResetAll, String nullString) {
		cbResetToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue==null) return;
			Object obj = mainClass.projectManager.getObject(fieldName, enumStep);
			if(obj==null) return;
			try {
				WrapperInteger wb = (WrapperInteger) obj;
				if (newValue) {
					Integer intReset = wb.resetDefault();
					tf.setText(intReset==null?nullString:Integer.toString(intReset));
					tf.setDisable(true);
					wb.setEnabled(false);}
				else {
					tf.setDisable(false);
					wb.setEnabled(true);
					if(cbResetAll!=null && cbResetAll.isSelected()) {allDefault=false;cbResetAll.setSelected(false);}
				}
			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Fail to cast! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
		});
	}
	protected void resetTextFieldDoubleListener(CheckBox cbResetToggle, TextField tf, String fieldName, CheckBox cbResetAll) {
		resetTextFieldDoubleListener(cbResetToggle, tf, fieldName, cbResetAll, "");
	}
	protected void resetTextFieldDoubleListener(CheckBox cbResetToggle, TextField tf, String fieldName, CheckBox cbResetAll, String nullString) {

		cbResetToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue==null) return;
			Object obj = mainClass.projectManager.getObject(fieldName, enumStep);
			if(obj==null) return;
			try {
				WrapperDouble wb = (WrapperDouble) obj;
				Double doubleReset = wb.resetDefault();
				if (newValue) {
					tf.setText(doubleReset==null?nullString:Double.toString(doubleReset));
					tf.setDisable(true);
					wb.setEnabled(false);}
				else {
					tf.setDisable(false);
					wb.setEnabled(true);
					if(cbResetAll!=null && cbResetAll.isSelected()) {allDefault=false;cbResetAll.setSelected(false);}
				}
			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Fail to cast! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
		});
	}
	protected <T extends EnumInProgram> void resetComboBoxListener(CheckBox cbResetToggle, ComboBox<T> cb, 
			String fieldName, CheckBox cbResetAll) {
		resetComboBoxListener(cbResetToggle, cb, fieldName, cbResetAll, false);
	}
	protected <T extends EnumInProgram> void resetComboBoxListener(CheckBox cbResetToggle, ComboBox<T> cb, 
			String fieldName, CheckBox cbResetAll, boolean notQEDefault) {
		//if notQEDefault is true, the default in the program is not the default of QE, so always enabled in the agent
		cbResetToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue==null) return;
			Object obj = mainClass.projectManager.getObject(fieldName, enumStep);
			if(obj==null) return;
			try {
				WrapperEnum wb = (WrapperEnum) obj;
				if (newValue) {
					cb.getSelectionModel().select((T) wb.resetDefault());
					cb.setDisable(true);
					wb.setEnabled(notQEDefault);}
				else {
					cb.setDisable(false);
					wb.setEnabled(true);
					if(cbResetAll!=null && cbResetAll.isSelected()) {allDefault=false;cbResetAll.setSelected(false);}
				}
			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Fail to cast! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
		});
	}
	
	protected Integer str2int(String str) {
    	try {
    		if(statusTextField!=null) {statusTextField.setText("");}
    		return Integer.parseInt(str);
    	}
    	catch(Exception e) {
    		if(statusTextField!=null) {statusTextField.setText("Error! Input is not integer. "+e.getMessage());}
    		return null;
    	}
    }
    protected Double str2double(String str) {
    	try {
    		if(statusTextField!=null) {statusTextField.setText("");}
    		return Double.parseDouble(str);
    	}
    	catch(Exception e) {
    		if(statusTextField!=null) {statusTextField.setText("Error! Input is not double. "+e.getMessage());}
    		return null;
    	}
    }
    protected void setInfoButton(Button bt,String key) {
    	bt.setTooltip(new Tooltip(QeDocumentation.pwShortDoc.get(key)));
    	bt.setOnAction((event) -> {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Info");
	    	alert1.setContentText(QeDocumentation.pwDoc.get(key));
	    	alert1.showAndWait();
		});
    }

    static protected void setField(TextField tf, WrapperDouble val) {
    	if(val.getValue()==null) tf.setText("");
    	else tf.setText(val.getValue().toString());
    }
    static protected void setField(TextField tf, WrapperInteger val) {
    	if(val.getValue()==null) tf.setText("");
    	else tf.setText(val.getValue().toString());
    }
    static protected <T> void setCombo(ComboBox<T> cb, WrapperEnum val) {
    	if(val.getValue()==null) cb.getSelectionModel().clearSelection();
    	else cb.setValue((T) val.getValue());
    }
    static protected void setToggle(ToggleButton tb, WrapperBoolean val) {
    	//val cannot be null!
    	tb.setSelected(val.getValue());
    }
    static protected void setCheck(CheckBox cb, Boolean bl) {
    	if(bl==null || cb==null) return;
    	cb.setSelected(bl);
    }
    protected void bindProperty(Label lb, ComboBox<?> cb) {
    	lb.textProperty().bind(cb.valueProperty().asString());
    }
    protected void bindProperty(Label lb, TextField tb) {
    	lb.textProperty().bind(tb.textProperty());
    }
}
