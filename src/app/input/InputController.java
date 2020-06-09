package app.input;

import java.lang.reflect.Field;

import com.consts.QeDocumentation;
import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumStep;

import agent.InputAgent;
import agent.InputAgentGeo;
import agent.InputAgentOpt;
import agent.InputAgentScf;
import agent.WrapperDouble;
import agent.WrapperInteger;
import javafx.fxml.Initializable;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.TextField;
import javafx.scene.control.Tooltip;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.Label;
import main.MainClass;

public abstract class InputController implements Initializable{
	
	protected MainClass mainClass;
	private Label statusTextField;//if existed, provides status information
	
	public InputController(MainClass mc) {
		mainClass = mc;
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
			
			InputAgent ia;
			Field fd=null;
			if(EnumStep.GEO.equals(es)) {ia = mainClass.projectManager.getCurrentGeoAgent();}
			else {ia = mainClass.projectManager.getStepAgent(es);}
			if (ia==null) return;
			try {
				switch(es) {
					case GEO:fd = InputAgentGeo.class.getField(fieldName);break;
					case SCF:fd = InputAgentScf.class.getField(fieldName);break;
					case OPT:fd = InputAgentOpt.class.getField(fieldName);break;
					case NSCF:
					case DOS:
					case BANDS:
					case BOMD:
					case TDDFT:break;
					default:break;
						
				}
				if(fd==null) {
					Alert alert1 = new Alert(AlertType.ERROR);
			    	alert1.setTitle("Error");
			    	alert1.setContentText("EnumStep undefined/not implemented detected in InputController!");
			    	alert1.showAndWait();
			    	return;
				}

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
						((WrapperDouble) fd.get(ia)).setValue(tmp);
						
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
						((WrapperInteger) fd.get(ia)).setValue(tmp);
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

			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Cannot set listener! "+e.getMessage());
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
}
