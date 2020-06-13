package app.input;

import java.lang.reflect.Field;

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
import main.MainClass;
import agent.InputAgent;
import agent.InputAgentDos;
import agent.InputAgentGeo;
import agent.InputAgentMd;
import agent.InputAgentNscf;
import agent.InputAgentOpt;
import agent.InputAgentScf;
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
	
	protected InputController(MainClass mc) {
		mainClass = mc;
		allDefault = false;
	}
	protected void setPointerStatusTextField(Label lb) {
		statusTextField = lb;
	}
	protected void setIntegerFieldListener(TextField tf, String fieldName, EnumNumCondition cond, EnumStep es) {	
		setFieldListener(tf, fieldName, cond, es, "int");
    }
	protected void setDoubleFieldListener(TextField tf, String fieldName, EnumNumCondition cond, EnumStep es) {	
		setFieldListener(tf, fieldName, cond, es, "double");
	}
	private void setFieldListener(TextField tf, String fieldName, EnumNumCondition cond, EnumStep es, String type) {	
		//type == "int"
		//type == "double"
		if(es==null) {
    		Alert alert1 = new Alert(AlertType.ERROR);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Cannot set listener! EnumStep is null. Abort..");
	    	alert1.showAndWait();
	    	return;
    	}
		tf.textProperty().addListener((observable, oldValue, newValue) -> {
			if(newValue==null) return;
			Object obj = getObject(fieldName, es);
			if(obj==null) return;
			try {
				if("double".equals(type)) {
					Double tmp = str2double(newValue);
					if (tmp!=null) {
						switch(cond) {
							case no:{break;}
							case positive:
								if(tmp<=0) {
									if(statusTextField!=null) {statusTextField.setText("Must be positive!");}
									return;
								} 
								break;
							case nonNegative:
								if(tmp<0) {
									if(statusTextField!=null) {statusTextField.setText("Must not be negative!");}
									return;
								} 
								break;
							default:
								break;
						}
						if(statusTextField!=null) {statusTextField.setText("");}
						((WrapperDouble) obj).setValue(tmp);
						
					}
				}
				else if("int".equals(type)) {
					Integer tmp = str2int(newValue);
					if (tmp!=null) {
						switch(cond) {
							case no:{break;}
							case positive:
								if(tmp<=0) {
									if(statusTextField!=null) {statusTextField.setText("Must be positive!");}
									return;
								} 
								break;
							case nonNegative:
								if(tmp<0) {
									if(statusTextField!=null) {statusTextField.setText("Must not be negative!");}
									return;
								} 
								break;
							default:
								break;
						}
						if(statusTextField!=null) {statusTextField.setText("");}
						((WrapperInteger) obj).setValue(tmp);
					}
				}
				else {
					Alert alert1 = new Alert(AlertType.ERROR);
			    	alert1.setTitle("Error");
			    	alert1.setContentText("Unimplemented type detected in InputController!");
			    	alert1.showAndWait();
			    	return;
				}
				if(EnumStep.GEO.equals(es)) {mainClass.projectManager.updateViewerPlot();}//update the plot if it is geo
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
	protected void setToggleListener(ToggleButton tb, String fieldName, EnumStep es, String onText, String offText) {	
		if(es==null || onText==null || offText==null || tb==null) {
    		Alert alert1 = new Alert(AlertType.ERROR);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Cannot set listener! EnumStep is null or on/off text is null. Abort..");
	    	alert1.showAndWait();
	    	return;
    	}
		//take care of the starting of the program
		if(tb.isSelected()) {tb.setText(onText);}
		else {tb.setText(offText);}
		
		tb.selectedProperty().addListener((observable, oldValue, newValue) -> {
			if(newValue==null) return;
			if(newValue) {tb.setText(onText);}
			else {tb.setText(offText);}
			Object obj = getObject(fieldName, es);
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
	protected <T extends EnumInProgram> void setComboListener(ComboBox<T> cb, T[] lstEnum, String fieldName, EnumStep es) {	
		if(es==null) {
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
			Object obj = getObject(fieldName, es);
			if(obj==null) return;
			try {
				if(statusTextField!=null) {statusTextField.setText("");}
				((WrapperEnum) obj).setValue((EnumInProgram) newValue);
				if(EnumStep.GEO.equals(es)) {mainClass.projectManager.updateViewerPlot();}//update the plot if it is geo
			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Fail to cast! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
		});
    }
	private Object getObject(String fieldName, EnumStep es) {
		InputAgent ia;
		Field fd=null;
		if(EnumStep.GEO.equals(es)) {ia = mainClass.projectManager.getCurrentGeoAgent();}
		else {ia = mainClass.projectManager.getStepAgent(es);}
		if (ia==null) return null;
		try {
			switch(es) {
				case GEO:fd = InputAgentGeo.class.getField(fieldName);break;
				case SCF:fd = InputAgentScf.class.getField(fieldName);break;
				case OPT:fd = InputAgentOpt.class.getField(fieldName);break;
				case NSCF:fd = InputAgentNscf.class.getField(fieldName);break;
				case DOS:fd = InputAgentDos.class.getField(fieldName);break;
				case BOMD:fd = InputAgentMd.class.getField(fieldName);break;
				case BANDS:
				case TDDFT:break;
				default:break;	
			}
			if(fd==null) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("EnumStep undefined/not implemented detected in InputController!");
		    	alert1.showAndWait();
		    	return null;
			}
			return fd.get(ia);

		} catch (Exception e) {
			Alert alert1 = new Alert(AlertType.ERROR);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Cannot find field! "+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
			return null;
		}
	}
	protected void resetToggleListener(CheckBox cbResetToggle, ToggleButton toggle, String fieldName, EnumStep es, CheckBox cbResetAll) {
		cbResetToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue==null) return;
			Object obj = getObject(fieldName, es);
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
					if(cbResetAll.isSelected()) {allDefault=false;cbResetAll.setSelected(false);}
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
	protected void resetTextFieldIntegerListener(CheckBox cbResetToggle, TextField tf, String fieldName, EnumStep es, CheckBox cbResetAll) {
		cbResetToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue==null) return;
			Object obj = getObject(fieldName, es);
			if(obj==null) return;
			try {
				WrapperInteger wb = (WrapperInteger) obj;
				if (newValue) {
					tf.setText(Integer.toString(wb.resetDefault()));
					tf.setDisable(true);
					wb.setEnabled(false);}
				else {
					tf.setDisable(false);
					wb.setEnabled(true);
					if(cbResetAll.isSelected()) {allDefault=false;cbResetAll.setSelected(false);}
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
	protected void resetTextFieldDoubleListener(CheckBox cbResetToggle, TextField tf, String fieldName, EnumStep es, CheckBox cbResetAll) {

		cbResetToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue==null) return;
			Object obj = getObject(fieldName, es);
			if(obj==null) return;
			try {
				WrapperDouble wb = (WrapperDouble) obj;
				if (newValue) {
					tf.setText(Double.toString(wb.resetDefault()));
					tf.setDisable(true);
					wb.setEnabled(false);}
				else {
					tf.setDisable(false);
					wb.setEnabled(true);
					if(cbResetAll.isSelected()) {allDefault=false;cbResetAll.setSelected(false);}
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
			String fieldName, EnumStep es, CheckBox cbResetAll) {
		resetComboBoxListener(cbResetToggle, cb, fieldName, es, cbResetAll, false);
	}
	protected <T extends EnumInProgram> void resetComboBoxListener(CheckBox cbResetToggle, ComboBox<T> cb, 
			String fieldName, EnumStep es, CheckBox cbResetAll, boolean notQEDefault) {
		//if notQEDefault is true, the default in the program is not the default of QE, so always enabled in the agent
		cbResetToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue==null) return;
			Object obj = getObject(fieldName, es);
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
					if(cbResetAll.isSelected()) {allDefault=false;cbResetAll.setSelected(false);}
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

    protected void setField(TextField tf, WrapperDouble val) {
    	if(val.getValue()==null) tf.setText("");
    	else tf.setText(val.getValue().toString());
    }
    protected void setField(TextField tf, WrapperInteger val) {
    	if(val.getValue()==null) tf.setText("");
    	else tf.setText(val.getValue().toString());
    }
    protected <T> void setCombo(ComboBox<T> cb, WrapperEnum val) {
    	if(val.getValue()==null) cb.getSelectionModel().clearSelection();
    	else cb.setValue((T) val.getValue());
    }
    protected void setToggle(ToggleButton tb, WrapperBoolean val) {
    	//val cannot be null!
    	tb.setSelected(val.getValue());
    }
}
