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

import java.util.ArrayList;

import app.input.geo.Atom;
import app.input.geo.Element;
import com.consts.ChemicalElements;
import com.consts.PhysicalConstants;
import com.consts.Constants.EnumFunctional;
import com.consts.Constants.EnumPP;
import com.consts.Constants.EnumUnitAtomPos;
import com.consts.Constants.EnumUnitCellAngle;
import com.consts.Constants.EnumUnitCellLength;
import com.consts.Constants.EnumUnitCellParameter;
import com.pseudopot.EnumPseudoPotLib;

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
	public String pseudodir;//pseudodir, careful, have to sync with ProjectManager.pseudoLibPath and settings of the lib
	
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
		//false means no update
		if(inputStr==null || inputStr.isEmpty()) {return false;}
		String upperCaseStr = inputStr.toUpperCase();
		if(inputStr.toUpperCase().contains("ATOMIC_POSITIONS")) {
			
		}
		if(inputStr.toUpperCase().contains("CELL_PARAMETERS")) {
			
		}
		return false;
	}
	public String genAgentSummary() {
		String msg="";
		if(ibrav.isNull() &&
				cellA.isNull() && cellB.isNull() && cellC.isNull() 
				&& cellAngleAB.isNull() && cellAngleBC.isNull() && cellAngleAC.isNull()) {
			msg+="No Bravais lattice information read.\n";//all default to null
		}
		else {
			//ibrav
			msg+=this.ibrav.isNull()?"":"ibrav="+this.ibrav.getValueString()+"\n";
			//lattice information
			msg += "A="+cellA.getValueString()+",B="+cellB.getValueString()+",C="+cellC.getValueString()+" (Unit:"
					+unitCellLength==null?"unknown":unitCellLength.toString()+")\n"
					+"AngleAB="+cellAngleAB.getValueString()+",AngleBC="+cellAngleBC.getValueString()+",AngleAC="+cellAngleAC.getValueString()+" (Unit:"
					+unitCellAngle==null?"unknown":unitCellAngle.toString()+")\n";
		}
		//atomic positions
		msg+=("Atomic poisitions (unit:"
		+this.unitAtomPos==null?"unknown":this.unitAtomPos.toString()
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
		+this.unitCellParameter==null?"unknown":this.unitCellParameter.toString()
		+"):\n");
		msg+=(this.vectorA1.getValueString()+","+this.vectorA2.getValueString()+","+this.vectorA3.getValueString()+"\n"
		+this.vectorB1.getValueString()+","+this.vectorB2.getValueString()+","+this.vectorB3.getValueString()+"\n"
		+this.vectorC1.getValueString()+","+this.vectorC2.getValueString()+","+this.vectorC3.getValueString()+"\n");
		
		return msg;
	}
}
