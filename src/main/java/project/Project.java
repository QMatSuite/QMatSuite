/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package project;

import java.io.IOException;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.HashMap;

import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;
import agent.InputAgent;
import agent.InputAgentGeo;
import app.centerwindow.WorkScene3D;
import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;
import com.error.ShowAlert;

import input.ContainerInputString;

public class Project implements Serializable{
	//EVRYTHING SHOULD BE ACCESSED ON THE PROJECT LEVEL, NOT ON THE CALCULATION CLASS LEVEL
	/**
	 * 
	 */
	private static final long serialVersionUID = 8311819691310573808L;
	
	private String nameProject;
	
	transient private HashMap<String, CalculationClass> calcDict;
	transient private ArrayList<String> calcList;
	transient private HashMap<EnumStep, InputAgent> projectDefault;
	transient private String activeCalcKey;
	transient private WorkScene3D viewer3D=null;
	transient private Boolean show3DScene;//if true, show 3D structure in the workspace. Otherwise show in/output files
	
	private ArrayList<InputAgentGeo> geoList;
	private Integer activeGeoInd;
	private Boolean boolGeoActive;
	private String calcScfDefault;
	

	
	private void readObject(java.io.ObjectInputStream in)throws IOException, ClassNotFoundException 
	{
		//for loading after serialization
	    in.defaultReadObject();
	    calcDict = new HashMap<String, CalculationClass>();
		calcList = new ArrayList<String>();
		projectDefault = new HashMap<EnumStep, InputAgent>();
		activeCalcKey = null;
		viewer3D = new WorkScene3D();
		//if(show3DScene==null) {show3DScene=true;}//make older version compatible with newer version
		show3DScene=true;//always show geometry when loading
	}
	
	public Project(String np) {
		show3DScene = true;
		activeCalcKey = null;
		nameProject = np;
		calcDict = new HashMap<String, CalculationClass>();
		calcList = new ArrayList<String>();
		projectDefault = new HashMap<EnumStep, InputAgent>();
		geoList = new ArrayList<InputAgentGeo>();
		geoList.add(new InputAgentGeo());//at least have one Geometry
		activeGeoInd = 0;
		boolGeoActive = true;
		calcScfDefault = null;
		viewer3D = new WorkScene3D();
	}
	public void setShow3DScene(Boolean bl) {
		show3DScene = bl;
	}
	public Boolean getShow3DScene() {
		return show3DScene;
	}
	public WorkScene3D getViewer3D() {
		if (viewer3D==null) {viewer3D = new WorkScene3D();}
		return viewer3D;
	}
	public void updateViewerPlot() {
		if (viewer3D==null) {viewer3D = new WorkScene3D();}
		viewer3D.buildGeometry(getAgentGeo());//null ok
		//viewer3D.buildSampleMolecule();
	}
	public void setGeoActive(Boolean bl) {
		boolGeoActive = bl;
	}
	public Boolean getGeoActive() {
		return boolGeoActive;
	}
	public void setProjectDefault(EnumStep es) {
		CalculationClass calc = getActiveCalc();
		if (calc==null) return;
		InputAgent ia = calc.getAgent(es);
		if (projectDefault!=null && ia!=null) {
			projectDefault.put(es, ia);//only reference
			calcScfDefault = activeCalcKey;//hopefully Enum does not need deep copy...
		}
	}
	public InputAgent getProjectDefault(EnumStep es) {
		if (es!=null && projectDefault!=null && projectDefault.containsKey(es)){
			return (InputAgent) projectDefault.get(es).clone();
		}
		else return null;
	}
	public Boolean isDefault() {
		if (calcScfDefault==null || activeCalcKey==null) return false;
		return java.util.Objects.equals(calcScfDefault,activeCalcKey);
	}
	
	public void addCalculation(EnumCalc ec) {
		String ecStr = genCalcName(ec);//ec can be null
		if(ecStr !=null) {
			addCalculation(ecStr, ec);
		}
	}
	private String genCalcName(EnumCalc ec) {
		if(ec==null) return null;
		String seedStr = ec.toString();
		int i=0;
		while(true) {
			i++;
			String out = (seedStr+"_"+i);
			if(!calcDict.containsKey(out)) return out;
		}
	}
	public void addCalculation(String calcName, CalculationClass cls) {
		if(cls!=null && calcName!=null && !calcName.isEmpty()) {
			if (!calcDict.containsKey(calcName)){
				if(!calcName.equals(cls.getCalcName())) {cls.setCalcName(calcName);}
				calcDict.put(calcName, cls);
				calcList.add(calcName);
			}
			activeCalcKey = calcName;
		}
	}
	public void addCalculation(String calcName, EnumCalc ec) {
		if (ec == null)  return;
		if (!calcDict.containsKey(calcName)){
			CalculationClass calc;
			switch (ec) {
			case SCF:calc = new CalculationScfClass(calcName);break;
			case OPT:calc = new CalculationOptClass(calcName);break;
			case DOS:calc = new CalculationDosClass(calcName);break;
			case BOMD:calc = new CalculationMdClass(calcName);break;
			case BANDS:calc = new CalculationBandsClass(calcName);break;
			case TDDFT:calc = new CalculationTddftClass(calcName);break;
			default:
				Alert alert = new Alert(AlertType.INFORMATION);
		    	alert.setTitle("Error");
		    	alert.setContentText("Not implemented CalculationClass!");
		    	alert.showAndWait();
		    	return;
			}
			if(!ec.equals(calc.getCalcType())) {
				ShowAlert.showAlert(AlertType.ERROR, "Error", "Inconsistent calculation type in addCalculation! Check programming!");
			}
			calcDict.put(calcName, calc);
			calcList.add(calcName);
		}
		activeCalcKey = calcName;//set active no matter whether already contains or not
	}
	public InputAgentGeo getAgentGeo() {
		if (activeGeoInd>=geoList.size()) return null;
		if (boolGeoActive || !existCurrentCalc()){
			return geoList.get(activeGeoInd);//use project default
		}
		else {
			Integer ind = getActiveCalc().getGeoInd();
			if (ind != null) {
				return geoList.get(getActiveCalc().getGeoInd());
			}
			else return null;
		}
	}
	public void setActiveGeoInd(int ind) {
		if (ind>=geoList.size()) return;
		activeGeoInd = ind;
	}
	public ArrayList<String> getCalcList(){
		return calcList;
	}
	public String getActiveCalcName() {
		return activeCalcKey;
	}
	public EnumCalc getCalcType(String calcName) {
		CalculationClass calcObj = getCalc(calcName);
		if(calcObj==null) return null;
		return calcObj.getCalcType();
	}
	public void setActiveCalcName(String ec) {
		if (ec!=null && calcDict.containsKey(ec)) {
			activeCalcKey=ec;
		}
	}
	public CalculationClass getActiveCalc() {
		if (activeCalcKey == null)  return null;
		if (calcDict.containsKey(activeCalcKey)) {
			return calcDict.get(activeCalcKey);
		}
		else return null;
	}
	public Boolean existCurrentCalc() {
		if (activeCalcKey == null)  return false;//no current calc
		return calcDict.containsKey(activeCalcKey);
	}
	public Boolean existCalc(String key) {
		if (key == null)  return false;
		return calcDict.containsKey(key);
	}
	public CalculationClass getCalc(String key) {
		if (key == null)  return null;
		if (calcDict.containsKey(key)) return calcDict.get(key);
		else return null;
	}
	public String getName() {
		return nameProject;
	}
	public void setName(String st) {
		nameProject = st;//no need to use new String(st)
	}
	public ArrayList<ContainerInputString> genInputFromAgent() {
		CalculationClass tmp = getActiveCalc();
		if (tmp==null || boolGeoActive) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setHeaderText("No valid calculation!");
	    	alert1.setContentText("No calculaion or in the geometry page.");
	    	alert1.showAndWait();
	    	return null;
		}
		else return tmp.genInputFromAgent(geoList);
	}
	public String getcalcScfDefault() {
		return calcScfDefault;
	}
	public void setcalcScfDefault(String calcScfDefault) {
		this.calcScfDefault = calcScfDefault;
	}
}
