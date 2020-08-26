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
package agent;

import java.io.File;
import java.util.ArrayList;
import java.util.Objects;

import app.input.geo.Atom;
import app.input.geo.Element;
import core.agent.InputAgent;
import core.agent.WrapperBoolean;
import core.agent.WrapperDouble;
import core.agent.WrapperInteger;
import core.com.consts.ChemicalElements;
import core.com.consts.PhysicalConstants;

import com.consts.Constants.EnumFunctional;
import com.consts.Constants.EnumPP;
import com.consts.Constants.EnumUnitAtomPos;
import com.consts.Constants.EnumUnitCellAngle;
import com.consts.Constants.EnumUnitCellLength;
import com.consts.Constants.EnumUnitCellParameter;
import com.programconst.DefaultFileNamesQE;
import com.pseudopot.EnumPseudoPotLib;
import com.pseudopot.PseudoPotential;

public class InputAgentGeo extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -7687077166066768185L;
	//helpers
	public boolean needAlatFromCell;
	public boolean needAlatFromAtom;
	//cell
	public WrapperInteger ibrav;//ok
	public EnumUnitCellLength unitCellLength;
	public EnumUnitCellAngle unitCellAngle;
	public WrapperDouble cellA;public WrapperDouble cellB;public WrapperDouble cellC;
	public WrapperDouble cellAngleBC;//alpha,celldm(5)
	public WrapperDouble cellAngleAC;//beta,celldm(6)
	public WrapperDouble cellAngleAB;//gamma,celldm(4)
	public EnumUnitCellParameter unitCellParameter;
	public WrapperDouble vectorA1;public WrapperDouble vectorA2;public WrapperDouble vectorA3;
	public WrapperDouble vectorB1;public WrapperDouble vectorB2;public WrapperDouble vectorB3;
	public WrapperDouble vectorC1;public WrapperDouble vectorC2;public WrapperDouble vectorC3;
	//atom
	public EnumUnitAtomPos unitAtomPos;//ok, will not be null
	public ArrayList<Atom> atomList;//ok
	//elements
	public EnumPseudoPotLib typeLib;
	public EnumFunctional typeFunctional;
	public EnumPP typePP;
	public Integer typePrec;
	public WrapperBoolean isRelativ;//whether or not fully relativistic
	public ArrayList<Element> elemListAll;
	private String pseudodir;//pseudodir, CAREFUL, have to sync with Psettings of the lib. No longer contains mainClass.projectManager.getPseudoLibPath()
	
	public InputAgentGeo() {

		//cell
		ibrav=new WrapperInteger(null);//no default//ok
		unitCellLength=EnumUnitCellLength.angstrom;
		unitCellAngle=EnumUnitCellAngle.degree;
		cellA=new WrapperDouble(null);cellB=new WrapperDouble(null);cellC=new WrapperDouble(null);//ok
		cellAngleAB=new WrapperDouble(null);cellAngleBC=new WrapperDouble(null);cellAngleAC=new WrapperDouble(null);//ok
		unitCellParameter=EnumUnitCellParameter.angstrom;
		vectorA1=new WrapperDouble(null);vectorA2=new WrapperDouble(null);vectorA3=new WrapperDouble(null);
		vectorB1=new WrapperDouble(null);vectorB2=new WrapperDouble(null);vectorB3=new WrapperDouble(null);
		vectorC1=new WrapperDouble(null);vectorC2=new WrapperDouble(null);vectorC3=new WrapperDouble(null);
		//atom
		unitAtomPos=EnumUnitAtomPos.alat;
		atomList=new ArrayList<Atom>();//for geoAtoms
		//elements
		typeLib = EnumPseudoPotLib.SSSP;
		typeFunctional=EnumFunctional.PBE;
		typePP=null;
		typePrec=0;
		isRelativ=new WrapperBoolean(false);
		elemListAll = new ArrayList<Element>();//for geoElements,scfMagnet
		
		//
		needAlatFromCell = false;
		needAlatFromAtom = unitAtomPos.equals(EnumUnitAtomPos.alat);
		
		pseudodir=null;
	}
	public boolean needCellA() {
		return needAlatFromCell || needAlatFromAtom;
	}
	public WrapperDouble convCellLength(WrapperDouble wd) {
		double scale = 1.0;
		//final main input file: angstrom for cellA,B,C
		switch (unitCellLength) {
			case angstrom:scale=1.0;break;
			case bohr:scale=1.0*PhysicalConstants.angstPerBohr;break;
			case pm:scale=1.0/100;break;
			default:return null;
		}
		return new WrapperDouble(wd.isNull()?null:wd.getValue()*scale,wd.isEnabled());
	}
	public WrapperDouble convCellAngle(WrapperDouble wd) {
		double scale = 1.0;
		//final main input file: angstrom for cellA,B,C
		switch (unitCellAngle) {
			case degree:scale=Math.PI/180.0;break;
			case radian:scale=1.0;break;
			default:return null;
		}
		return new WrapperDouble(wd.isNull()?null:Math.cos(wd.getValue()*scale),wd.isEnabled());
	}
	public void updateElemListAll() {
		for (Atom tmp_atom : atomList) {
			if(!elemListAllContains(tmp_atom.getAtomSpecies())) {
				elemListAll.add(new Element(tmp_atom.getAtomSpecies()));
			}
		}
		for (int i=0;i<elemListAll.size();i++) {
			if(!atomListContains(elemListAll.get(i).getAtomSpecies())) {
				elemListAll.remove(i);
			}
		}
	}
	private Boolean atomListContains(ChemicalElements species) {
		for (Atom tmp_atom : atomList) {
			if(tmp_atom.getAtomSpecies().toString().equals(species.toString())) {return true;}
		}
		return false;
	}
	private Boolean elemListAllContains(ChemicalElements species) {
		for (Element tmp_elem : elemListAll) {
			if(tmp_elem.getAtomSpecies().toString().equals(species.toString())) {return true;}
		}
		return false;
	}
	public ArrayList<String> getElementStringList() {
		ArrayList<String> elem = new ArrayList<String>();
		for (Atom tmp : atomList) {
			if(!elem.contains(tmp.getAtomSpecies().toString())) {
				elem.add(tmp.getAtomSpecies().toString());
			}
		}
		return elem;
	}
	@Override
	public boolean convertInfoFromInput(String inputStr) {
		//false means no change
		boolean flagChange = false;
		if(inputStr==null || inputStr.isEmpty()) {return false;}
		
		if(getAtomicPositions(inputStr)) {flagChange=true;}//this is not change based true/false. Once keyword detected, then true
		if(getCellParameters(inputStr)) {flagChange=true;}//this is not change based true/false. Once keyword detected, then true
		
		//ibrav
		//do not have to worry about improper input (tmp <0 or tmp>14). Will be corrected in the 
		//input controllers while loading inputagents
		if(setParameterValue("ibrav", inputStr, this.ibrav)) {flagChange=true;}

		//A,B,C,AB,BC,AC
		boolean flagABC = false;
		if(setParameterValue("A",inputStr, this.cellA)) {flagABC=true;}
		if(setParameterValue("B",inputStr, this.cellB)) {flagABC=true;}
		if(setParameterValue("C",inputStr, this.cellC)) {flagABC=true;}
		if(setParameterValueArccos("cosAB",inputStr, this.cellAngleAB)) {flagABC=true;}
		if(setParameterValueArccos("cosBC",inputStr, this.cellAngleBC)) {flagABC=true;}
		if(setParameterValueArccos("cosAC",inputStr, this.cellAngleAC)) {flagABC=true;}
		if(flagABC) {
			flagChange = true;
			this.unitCellLength = EnumUnitCellLength.angstrom;
			this.unitCellAngle = EnumUnitCellAngle.degree;
		}
		else {
			//now try celldm. The two languages must not coexist in the input file as required by QE
			boolean flagCelldm = false;
			if(setParameterValueCelldm("celldm\\(1\\)",inputStr, 1)) {flagCelldm=true;}//this (1) must go before others (2-6)
			if(setParameterValueCelldm("celldm\\(2\\)",inputStr, 2)) {flagCelldm=true;}
			if(setParameterValueCelldm("celldm\\(3\\)",inputStr, 3)) {flagCelldm=true;}
			if(setParameterValueCelldm("celldm\\(4\\)",inputStr, 4)) {flagCelldm=true;}//ibrav must go before these (4-6)
			if(setParameterValueCelldm("celldm\\(5\\)",inputStr, 5)) {flagCelldm=true;}
			if(setParameterValueCelldm("celldm\\(6\\)",inputStr, 6)) {flagCelldm=true;}
			
			//ShowAlert.showAlert(AlertType.INFORMATION, "Warning", flagCelldm?"true":"false");
			//if existed celldm, change unit to bohr
			if(flagCelldm) {
				flagChange = true;
				this.unitCellLength = EnumUnitCellLength.bohr;
				this.unitCellAngle = EnumUnitCellAngle.degree;
			}
		}
		
		return flagChange;
	}
	private boolean setParameterValueArccos(String paraStr, String inputStr, WrapperDouble wdVal) {
		Double tmp = null;
		try {
			String strTmp = getParameterValue(paraStr,inputStr);
			if(strTmp==null) {return false;}//when getParameterValue(paraStr,inputStr)==null -> keyword not found
			tmp = Double.valueOf(strTmp);
			if(tmp!=null && tmp<=1.0 && tmp >=-1.0) {tmp = Math.toDegrees(Math.acos(tmp));}
			else {
				tmp=null;
			}
		}
		catch(IllegalArgumentException e) {
			tmp=null;
		}
		if(Objects.equals(wdVal.getValue(), tmp)) {
			return false;
		}
		else {
			wdVal.setValue(tmp);return true;
		}
	}
	private boolean setParameterValueCelldm(String paraStr, String inputStr, int celldmInd) {
		Double tmp = null;
		try {
			String strTmp = getParameterValue(paraStr,inputStr);
			if(strTmp==null) {return false;}//when getParameterValue(paraStr,inputStr)==null -> keyword not found
			tmp = Double.valueOf(strTmp);
			return setCellABCFromCelldm(celldmInd, tmp);
		}
		catch(IllegalArgumentException e) {
			return setCellABCFromCelldm(celldmInd, null);
		}
	}
	public boolean setCellABCFromCelldm(int celldmInd, Double celldmVal) {
		
		//!!!!must first load celldm(1), otherwise cannot load celldm(2) and celldm(3)
		//!!!!must first load ibrav, otherwise celldm(4) and (6) not correct
		boolean isChanged = false;
		final Double tmp = (celldmVal==null || celldmVal>1.0 || celldmVal<-1.0)?null:Math.toDegrees(Math.acos(celldmVal));
		switch(celldmInd) {
			case 1:
				isChanged=!cellA.equals(celldmVal);
				//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", cellA.getValueString()+","+celldmVal+","+(isChanged?"changed":"no"));
				cellA.setValue(celldmVal);
				break;
			case 2:
				if(!cellA.isNull()) {isChanged=!cellB.equals(cellA.getValue()*celldmVal);cellB.setValue(cellA.getValue()*celldmVal);}//cellA must be not null
				break;
			case 3:
				if(!cellA.isNull()) {isChanged=!cellC.equals(cellA.getValue()*celldmVal);cellC.setValue(cellA.getValue()*celldmVal);}
				break;
			case 4:
				if(ibrav.equals(14)) {
					isChanged = !cellAngleBC.equals(tmp);
					cellAngleBC.setValue(tmp);
				}
				else {
					isChanged = !cellAngleAB.equals(tmp);
					cellAngleAB.setValue(tmp);
				}
				break;
			case 5:
				isChanged = !cellAngleAC.equals(tmp);
				cellAngleAC.setValue(tmp);
				break;
			case 6:
				if(ibrav.equals(14)) {
					isChanged = !cellAngleAB.equals(tmp);
					cellAngleAB.setValue(tmp);
				}
				else {
					isChanged = !cellAngleBC.equals(tmp);
					cellAngleBC.setValue(tmp);
				}
				break;
			default:break;
		}
		
		return isChanged;
	}
	private boolean getCellParameters(String inputStr) {	
		//return true for detecting keyword
		int startInd;
		startInd = inputStr.toUpperCase().indexOf("CELL_PARAMETERS");
		if(startInd==-1) {return false;}
		
		this.vectorA1.setValue(null);this.vectorA2.setValue(null);this.vectorA3.setValue(null);
		this.vectorB1.setValue(null);this.vectorB2.setValue(null);this.vectorB3.setValue(null);
		this.vectorC1.setValue(null);this.vectorC2.setValue(null);this.vectorC3.setValue(null);
		
		String[] lines = inputStr.substring(startInd).split("\\R");
		//unit of cell parameters
		if(lines[0].toLowerCase().contains("alat")) {
			this.unitCellParameter = EnumUnitCellParameter.alat;
		}else if(lines[0].toLowerCase().contains("bohr")) {
			this.unitCellParameter = EnumUnitCellParameter.bohr;
		}else if(lines[0].toLowerCase().contains("angstrom")) {
			this.unitCellParameter = EnumUnitCellParameter.angstrom;
		}else {
			this.unitCellParameter = EnumUnitCellParameter.alat;
		}
		
		//load atomic positions
		int countCell = 1;
		for(int i=1;i<lines.length;i++) {//starting from 1 to skip the line containing "CELL_PARAMETERS"
			if(lines[i].trim().isEmpty()) {continue;}//skip empty lines
			if(!getCellParameterLine(lines[i],countCell)) {break;}//break if the line does not contain cell parameters
			else {
				countCell+=1;
			}
		}

		return true;
	}
	private boolean getCellParameterLine(String inputLine, int countCell) {
		//false means not containing atomic positions
		String[] splitted = inputLine.trim().split("\\s+");//split the string by whitespaces
		if(splitted.length < 3) {return false;}
		try {
			Double x_coor = Double.valueOf(splitted[0].trim());
			Double y_coor = Double.valueOf(splitted[1].trim());
			Double z_coor = Double.valueOf(splitted[2].trim());
			
			if(x_coor==null || y_coor == null || z_coor == null) {return false;}
			
			if(countCell==1) {
				this.vectorA1.setValue(x_coor);this.vectorA2.setValue(y_coor);this.vectorA3.setValue(z_coor);
			}
			else if(countCell==2) {
				this.vectorB1.setValue(x_coor);this.vectorB2.setValue(y_coor);this.vectorB3.setValue(z_coor);
			}
			else if(countCell==3) {
				this.vectorC1.setValue(x_coor);this.vectorC2.setValue(y_coor);this.vectorC3.setValue(z_coor);
			}else {
				return false;
			}
			return true;
		}
		catch(IllegalArgumentException e){
			//e.printStackTrace();
			return false;
		}
	}
	private boolean getAtomicPositions(String inputStr) {	
		//return true for detecting keyword
		int startInd;
		startInd = inputStr.toUpperCase().indexOf("ATOMIC_POSITIONS");
		if(startInd==-1) {return false;}
		
		atomList.clear();
		
		String[] lines = inputStr.substring(startInd).split("\\R");
		//unit of atomic positions
		if(lines[0].toLowerCase().contains("alat")) {
			this.unitAtomPos = EnumUnitAtomPos.alat;
		}else if(lines[0].toLowerCase().contains("bohr")) {
			this.unitAtomPos = EnumUnitAtomPos.bohr;
		}else if(lines[0].toLowerCase().contains("angstrom")) {
			this.unitAtomPos = EnumUnitAtomPos.angstrom;
		}else if(lines[0].toLowerCase().contains("crystal")) {
			this.unitAtomPos = EnumUnitAtomPos.crystal;
		}else {
			this.unitAtomPos = EnumUnitAtomPos.alat;//deprecated usage of QE
		}
		//load atomic positions
		for(int i=1;i<lines.length;i++) {//starting from 1 to skip the line containing "ATOMIC_POSITIONS"
			if(lines[i].trim().isEmpty()) {continue;}//skip empty lines
			if(!getAtomicPositionsLine(atomList,lines[i])) {break;}//break if the line does not contain atomic positions
		}
		//write to atomList and update elementList if atomArr is not empty
		updateElemListAll();
		return true;
	}
	
	private boolean getAtomicPositionsLine(ArrayList<Atom> atomArr, String inputLine) {
		//false means not containing atomic positions
		String[] splitted = inputLine.trim().split("\\s+");//split the string by whitespaces
		if(splitted.length < 4) {return false;}
		try {
			ChemicalElements atomSpecies = ChemicalElements.valueOf(splitted[0].trim());
			Double x_coor = Double.valueOf(splitted[1].trim());
			Double y_coor = Double.valueOf(splitted[2].trim());
			Double z_coor = Double.valueOf(splitted[3].trim());
			
			if(x_coor==null || y_coor == null || z_coor == null || atomSpecies == null) {return false;}
			
			if(splitted.length >=7) {
				Boolean free_x = strToBool(splitted[4].trim());
				Boolean free_y = strToBool(splitted[5].trim());
				Boolean free_z = strToBool(splitted[6].trim());
				if(free_x != null && free_y != null && free_z != null) {
					//Atom takes fixed bool, not free bool that usually exists in the input file
					atomArr.add(new Atom(atomSpecies,x_coor,y_coor,z_coor,!free_x,!free_y,!free_z));
				}
				else {
					atomArr.add(new Atom(atomSpecies,x_coor,y_coor,z_coor));
				}
			}
			else {
				atomArr.add(new Atom(atomSpecies,x_coor,y_coor,z_coor));
			}
			return true;
		}
		catch(IllegalArgumentException e){
			//e.printStackTrace();
			return false;
		}
	}
	private Boolean strToBool(String strVal) {
		if(strVal==null) {return null;}
		if("1".equals(strVal.trim())) {return true;}
		else if("0".equals(strVal.trim())) {return false;}
		else {return null;}
	}
	private boolean isCellABCAllNull() {
		return cellA.isNull() && cellB.isNull() && cellC.isNull() 
				&& cellAngleAB.isNull() && cellAngleBC.isNull() && cellAngleAC.isNull();
	}
	public String genAgentSummary() {
		String msg="";
		if(ibrav.isNull() && isCellABCAllNull()) {
			msg+="No Bravais lattice information read.\n";//all default to null
		}
		else {
			//ibrav
			msg+=this.ibrav.isNull()?"ibrav null.":"ibrav="+this.ibrav.getValueString()+"\n";
			//lattice information
			msg += "A="+cellA.getValueString()+",B="+cellB.getValueString()+",C="+cellC.getValueString()+" (Unit:"
					+(unitCellLength==null?"unknown":unitCellLength.toString())+")\n"
					+"AngleAB="+cellAngleAB.getValueString()+",AngleBC="+cellAngleBC.getValueString()+",AngleAC="+cellAngleAC.getValueString()+" (Unit:"
					+(unitCellAngle==null?"unknown":unitCellAngle.toString())+")\n";
		}
		//atomic positions
		msg+=("Atomic poisitions (unit:"
		+(this.unitAtomPos==null?"unknown":this.unitAtomPos.toString())
		+"):\n");
		for(Atom atom : this.atomList) {
			if(atom.getAtomSpecies()==null) {continue;}
			msg += ("" + atom.getAtomSpecies().toString()
					+ ":" + atom.getXcoor().getXString() + "," + atom.getYcoor().getXString() + "," + atom.getZcoor().getXString()
					 + "," + atom.getXcoor().getFixString() + "," + atom.getYcoor().getFixString() + "," + atom.getZcoor().getFixString()
					 +"\n");
		}
		//cell parameters
		msg+=("Cell parameters (unit:"
		+(this.unitCellParameter==null?"unknown":this.unitCellParameter.toString())
		+"):\n");
		msg+=(this.vectorA1.getValueString()+","+this.vectorA2.getValueString()+","+this.vectorA3.getValueString()+"\n"
		+this.vectorB1.getValueString()+","+this.vectorB2.getValueString()+","+this.vectorB3.getValueString()+"\n"
		+this.vectorC1.getValueString()+","+this.vectorC2.getValueString()+","+this.vectorC3.getValueString()+"\n");
		
		return msg;
	}
	public String getPseudodir() {
		if(pseudodir==null) {return null;}
		//to be compatible with previous versions, where the root folder is included
		int i1 = pseudodir.indexOf(DefaultFileNamesQE.pseudoDojoDir);
		int i2 = pseudodir.indexOf(DefaultFileNamesQE.psLibraryDir);
		int i3 = pseudodir.indexOf(DefaultFileNamesQE.ssspDir);
		if(i1!=-1) {
			pseudodir=pseudodir.substring(i1);
		}
		if(i2!=-1) {
			pseudodir=pseudodir.substring(i2);
		}
		if(i3!=-1) {
			pseudodir=pseudodir.substring(i3);
		}
		return (new File(PseudoPotential.getRootFolder(),pseudodir)).getAbsolutePath();
	}
	public void setPseudodir(String pseudodir) {
		this.pseudodir = pseudodir;//without root folder directory
	}
}
