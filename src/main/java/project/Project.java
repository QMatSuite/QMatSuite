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
import app.input.CellParameter;
import app.input.geo.Atom;

import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumUnitAtomPos;
import com.consts.Constants.EnumUnitCellLength;
import com.consts.Constants.EnumUnitCellParameter;
import com.error.ShowAlert;

import input.ContainerInputString;

public class Project implements Serializable{
	//EVRYTHING SHOULD BE ACCESSED AT LEAST ON THE PROJECT LEVEL, NOT ON THE CALCULATION CLASS LEVEL
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
	
	private ArrayList<InputAgentGeo> geoList;
	private ArrayList<String> geoName;
	private Integer activeGeoInd;
	private boolean boolGeoActive;
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
	}
	
	public Project(String np) {
		activeCalcKey = null;
		nameProject = np;
		calcDict = new HashMap<String, CalculationClass>();
		calcList = new ArrayList<String>();
		geoName = new ArrayList<String>();
		projectDefault = new HashMap<EnumStep, InputAgent>();
		geoList = new ArrayList<InputAgentGeo>();
		geoList.add(new InputAgentGeo());//at least have one Geometry
		geoName.add("Original");//at least have one Geometry
		activeGeoInd = 0;
		boolGeoActive = true;
		calcScfDefault = null;
		viewer3D = new WorkScene3D();
	}
	public ArrayList<String> getGeoName(){
		return geoName;
	}
	public boolean removeGeoList(int ind) {
		if(ind<0 || ind>geoList.size()) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Geometry deleted out of bound.");
			return false;
		}
		if(ind==0) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Cannot delete the first geometry (the original one).");
			return false;
		}
		for(CalculationClass calc : calcDict.values()) {
			if(calc==null) {continue;}
			if(calc.getGeoInd()==ind) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Calculation "+calc.calcName+
						" uses the geometry to be deleted ("+Integer.toString(ind+1)+"th). Change that and save first and then delete.");
				return false;
			}
		}
		geoList.remove(ind);geoName.remove(ind);
		if(activeGeoInd!=null && activeGeoInd>=ind) {activeGeoInd-=1;}
		return true;
	}
	public boolean duplicateGeoList(int ind) {
		if(ind<0 || ind>geoList.size()) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Geometry deleted out of bound.");
			return false;
		}
		geoList.add((InputAgentGeo)geoList.get(ind).deepCopy());
		geoName.add(geoName.get(ind)+"_copy");
		return true;
	}
	private void findAndAddGeo(String calcFolderName,InputAgentGeo iGeoCopy) {
		String msg="";
		int indexName = geoName.indexOf(calcFolderName);
		if(indexName==-1) {geoList.add(iGeoCopy);geoName.add(calcFolderName);msg="Successfully added "+Integer.toString(geoList.size());}
		else {geoList.set(indexName,iGeoCopy);msg="Successfully modified "+Integer.toString(indexName+1);}
		
		ShowAlert.showAlert(AlertType.INFORMATION, "Geometry added", msg+"th geometry");
	}
	public void addGeoList(String calcFolderName, InputAgentGeo iGeo) {
		InputAgentGeo iGeoCopy = (InputAgentGeo) iGeo.deepCopy();//clone the inputAgentGeo
		findAndAddGeo(calcFolderName,iGeoCopy);
	}
	public void addGeoList(String calcFolderName, ArrayList<Atom> atomList, CellParameter cellPara, Double alat) {
		if(alat==null || atomList==null || atomList.isEmpty() || 
				calcFolderName==null || !calcDict.containsKey(calcFolderName)) {return;}
		CalculationClass calcClass = calcDict.get(calcFolderName);
		Integer indGeo = calcClass.getGeoInd();
		if(indGeo==null || indGeo<0 || indGeo>=geoList.size()) {return;}

		InputAgentGeo iGeo = (InputAgentGeo) geoList.get(indGeo).deepCopy();//clone the inputAgentGeo. Check whether works or not
		
		iGeo.unitCellLength=EnumUnitCellLength.bohr;
		iGeo.unitAtomPos=EnumUnitAtomPos.alat;
		iGeo.atomList.clear();
		iGeo.atomList = atomList;
		
		if(cellPara!=null) {
			iGeo.ibrav.setValue(0);//0 is free cell
			iGeo.unitCellParameter=EnumUnitCellParameter.alat;
			iGeo.vectorA1.setValue(cellPara.getAx());
			iGeo.vectorA2.setValue(cellPara.getAy());
			iGeo.vectorA3.setValue(cellPara.getAz());
			iGeo.vectorB1.setValue(cellPara.getBx());
			iGeo.vectorB2.setValue(cellPara.getBy());
			iGeo.vectorB3.setValue(cellPara.getBz());
			iGeo.vectorC1.setValue(cellPara.getCx());
			iGeo.vectorC2.setValue(cellPara.getCy());
			iGeo.vectorC3.setValue(cellPara.getCz());
		}
		
		iGeo.updateElemListAll();

		findAndAddGeo(calcFolderName,iGeo);
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
	public void setGeoActive(boolean bl) {
		boolGeoActive = bl;
	}
	public boolean getGeoActive() {
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
			return (InputAgent) projectDefault.get(es).deepCopy();
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
			return geoList.get(getActiveCalc().getGeoInd());
		}
	}
	public void setAgentGeo(InputAgentGeo iGeo) {
		if (activeGeoInd>=geoList.size()) return;
		if (boolGeoActive || !existCurrentCalc()){
			geoList.set(activeGeoInd,iGeo);//use project default
		}
		else {
			geoList.set(getActiveCalc().getGeoInd(),iGeo);
		}
	}
	public Integer getGeoListSize() {
		if(geoList==null) {return 0;}
		return geoList.size();
	}
	public Integer getActiveGeoInd() {
		if(boolGeoActive) {
			//if the main window is in the geometry page
			return activeGeoInd;
		}
		else {
			//if the main window is in the calculation page
			CalculationClass calc = getActiveCalc();
			if(calc==null) {return null;}
			return calc.getGeoInd();
		}
	}
	public void setActiveGeoInd(int ind) {
		if (ind>=geoList.size()) return;
		if(boolGeoActive) {
			//if the main window is in the geometry page
			activeGeoInd = ind;
			//ShowAlert.showAlert(AlertType.INFORMATION, "Info", "Geometry changed in geometry: "+Integer.toString(ind));
		}
		else {
			//if the main window is in the calculation page
			CalculationClass calc = getActiveCalc();
			if(calc==null) {return;}
			calc.setGeoInd(ind);
			//ShowAlert.showAlert(AlertType.INFORMATION, "Info", "Geometry changed in calculation "+calc.getCalcName()+": "+Integer.toString(ind));
		}
		
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
